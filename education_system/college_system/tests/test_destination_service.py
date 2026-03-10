"""Tests for DestinationService."""

import pytest

from education_system.college_system.modules.domain.destinations.services.destination_service import DestinationService
from education_system.college_system.core.exceptions import DestinationError


class TestDestinationService:
    def test_create_destination(self, db_path, sample_student):
        svc = DestinationService(db_path)
        dest = svc.create_destination(
            sample_student["id"], academic_year="2025/26",
            destination_type="university",
            institution_name="University of Oxford",
        )
        assert dest["destination_type"] == "university"
        assert dest["neet_risk"] == 0

    def test_list_destinations(self, db_path, sample_student):
        svc = DestinationService(db_path)
        svc.create_destination(sample_student["id"], destination_type="university")
        svc.create_destination(sample_student["id"], destination_type="employment")
        dests = svc.list_destinations()
        assert len(dests) >= 2

    def test_confirm_destination(self, db_path, sample_student):
        svc = DestinationService(db_path)
        dest = svc.create_destination(sample_student["id"])
        confirmed = svc.confirm_destination(dest["id"], "BSc Computer Science", "university")
        assert confirmed["confirmed_destination"] == "BSc Computer Science"
        assert confirmed["destination_type"] == "university"

    def test_flag_neet_risk(self, db_path, sample_student):
        svc = DestinationService(db_path)
        dest = svc.create_destination(sample_student["id"])
        flagged = svc.flag_neet_risk(dest["id"])
        assert flagged["neet_risk"] == 1

    def test_neet_risk_students(self, db_path, sample_student):
        svc = DestinationService(db_path)
        dest = svc.create_destination(sample_student["id"])
        svc.flag_neet_risk(dest["id"])
        students = svc.get_neet_risk_students()
        assert len(students) >= 1

    def test_record_contact(self, db_path, sample_student):
        svc = DestinationService(db_path)
        dest = svc.create_destination(sample_student["id"])
        contacted = svc.record_contact(dest["id"])
        assert contacted["contact_made"] == 1

    def test_pending_followups(self, db_path, sample_student):
        svc = DestinationService(db_path)
        svc.create_destination(sample_student["id"])
        followups = svc.get_pending_followups()
        assert len(followups) >= 1

    def test_destination_stats(self, db_path, sample_student):
        svc = DestinationService(db_path)
        svc.create_destination(sample_student["id"], destination_type="university")
        stats = svc.get_destination_stats()
        assert stats["total"] >= 1

    def test_calculate_neet_risk(self, db_path, sample_student):
        svc = DestinationService(db_path)
        svc.create_destination(sample_student["id"])
        result = svc.calculate_neet_risk(sample_student["id"])
        assert "risk_score" in result
        assert result["risk_level"] in ("low", "medium", "high")
