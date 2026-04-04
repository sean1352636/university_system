"""Tests for HealthSafetyService."""

import pytest


class TestHealthSafetyService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.health_safety.services.health_safety_service import HealthSafetyService
        return HealthSafetyService(db_path)

    def test_create_incident(self, service):
        incident = service.create_incident(
            incident_date="2026-03-15",
            description="Student slipped on wet floor in corridor B",
            incident_type="slip_trip_fall", location="Corridor B",
        )
        assert incident is not None

    def test_list_incidents(self, service):
        service.create_incident("2026-03-15", "Incident A")
        service.create_incident("2026-03-16", "Incident B")
        incidents = service.list_incidents()
        assert len(incidents) >= 2

    def test_get_incident(self, service):
        incident = service.create_incident("2026-03-15", "Test incident")
        iid = incident if isinstance(incident, int) else incident.get("id", incident)
        found = service.get_incident(iid)
        assert found is not None

    def test_update_incident(self, service):
        incident = service.create_incident("2026-03-15", "Minor bump")
        iid = incident if isinstance(incident, int) else incident.get("id", incident)
        updated = service.update_incident(iid, status="investigating")
        assert updated is not None

    def test_delete_incident(self, service):
        incident = service.create_incident("2026-03-15", "Delete me")
        iid = incident if isinstance(incident, int) else incident.get("id", incident)
        result = service.delete_incident(iid)
        assert result is True or result is None

    def test_close_incident(self, service):
        incident = service.create_incident("2026-03-15", "To close")
        iid = incident if isinstance(incident, int) else incident.get("id", incident)
        closed = service.close_incident(
            iid, root_cause="Wet floor not signed",
            corrective_actions="Added wet floor sign protocol",
        )
        assert closed is not None

    def test_create_inspection(self, service):
        insp = service.create_inspection(
            inspection_type="fire_safety",
            inspection_date="2026-04-01",
            location="Main Building",
        )
        assert insp is not None

    def test_list_inspections(self, service):
        service.create_inspection("electrical", "2026-04-01")
        inspections = service.list_inspections()
        assert len(inspections) >= 1

    def test_create_risk_assessment(self, service):
        ra = service.create_risk_assessment(
            activity="Chemistry practical",
            assessment_date="2026-04-01",
            risk_rating="medium",
        )
        assert ra is not None

    def test_list_risk_assessments(self, service):
        service.create_risk_assessment("Lab work", "2026-04-01")
        ras = service.list_risk_assessments()
        assert len(ras) >= 1

    def test_create_compliance_check(self, service):
        check = service.create_compliance_check(
            check_type="fire_extinguisher",
        )
        assert check is not None

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
