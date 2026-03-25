"""Tests for ComplianceService (funding records, resit tracking, destinations)."""

import pytest

from education_system.college_system.modules.domain.compliance.services.compliance_service import ComplianceService
from education_system.college_system.core.exceptions import ComplianceError


class TestComplianceFundingRecords:
    @pytest.fixture
    def compliance_service(self, db_path):
        return ComplianceService(db_path)

    def test_create_funding_record(self, compliance_service, sample_student):
        record = compliance_service.create_funding_record(
            student_id=sample_student["id"],
            learning_aim="A-Level Maths",
            funding_model="16-19",
            planned_hours=540,
        )
        assert record["student_id"] == sample_student["id"]
        assert record["planned_hours"] == 540

    def test_list_funding_records_all(self, compliance_service, sample_student):
        compliance_service.create_funding_record(
            student_id=sample_student["id"],
            learning_aim="A-Level English", funding_model="16-19",
        )
        records = compliance_service.list_funding_records()
        assert len(records) >= 1

    def test_list_funding_records_by_student(self, compliance_service, sample_student):
        compliance_service.create_funding_record(
            student_id=sample_student["id"],
            learning_aim="A-Level Science", funding_model="16-19",
        )
        records = compliance_service.list_funding_records(student_id=sample_student["id"])
        assert len(records) >= 1
        assert all(r["student_id"] == sample_student["id"] for r in records)

    def test_update_funding_record(self, compliance_service, sample_student):
        record = compliance_service.create_funding_record(
            student_id=sample_student["id"],
            learning_aim="A-Level History", funding_model="16-19",
            planned_hours=100,
        )
        updated = compliance_service.update_funding_record(
            record["id"], actual_hours=80,
        )
        assert updated["actual_hours"] == 80

    def test_update_funding_record_no_valid_fields(self, compliance_service, sample_student):
        record = compliance_service.create_funding_record(
            student_id=sample_student["id"],
            learning_aim="A-Level Geography", funding_model="16-19",
        )
        with pytest.raises(ComplianceError, match="No valid fields"):
            compliance_service.update_funding_record(record["id"], bad_field="nope")

    def test_delete_record(self, compliance_service, sample_student):
        record = compliance_service.create_funding_record(
            student_id=sample_student["id"],
            learning_aim="A-Level Art", funding_model="16-19",
        )
        assert compliance_service.delete_record(record["id"]) is True

    def test_delete_record_not_found(self, compliance_service):
        with pytest.raises(ComplianceError, match="not found"):
            compliance_service.delete_record(99999)


class TestComplianceResitTracking:
    @pytest.fixture
    def compliance_service(self, db_path):
        return ComplianceService(db_path)

    def test_create_resit(self, compliance_service, sample_student):
        resit = compliance_service.create_resit(
            student_id=sample_student["id"],
            subject="english",
            gcse_grade_on_entry="3",
            target_grade="4",
            resit_required=1,
        )
        assert resit["subject"] == "english"
        assert resit["gcse_grade_on_entry"] == "3"

    def test_list_resits_all(self, compliance_service, sample_student):
        compliance_service.create_resit(
            student_id=sample_student["id"],
            subject="english",
        )
        resits = compliance_service.list_resits()
        assert len(resits) >= 1

    def test_list_resits_by_student(self, compliance_service, sample_student):
        compliance_service.create_resit(
            student_id=sample_student["id"],
            subject="maths",
        )
        resits = compliance_service.list_resits(student_id=sample_student["id"])
        assert len(resits) >= 1

    def test_list_resits_by_status(self, compliance_service, sample_student):
        compliance_service.create_resit(
            student_id=sample_student["id"],
            subject="english",
        )
        active = compliance_service.list_resits(status="active")
        assert all(r["status"] == "active" for r in active)

    def test_update_resit(self, compliance_service, sample_student):
        resit = compliance_service.create_resit(
            student_id=sample_student["id"],
            subject="maths",
        )
        updated = compliance_service.update_resit(
            resit["id"], status="achieved", latest_result="4",
        )
        assert updated["status"] == "achieved"
        assert updated["latest_result"] == "4"

    def test_update_resit_no_valid_fields(self, compliance_service, sample_student):
        resit = compliance_service.create_resit(
            student_id=sample_student["id"],
            subject="english",
        )
        with pytest.raises(ComplianceError, match="No valid fields"):
            compliance_service.update_resit(resit["id"], bad_field="nope")


class TestComplianceDestinations:
    @pytest.fixture
    def compliance_service(self, db_path):
        return ComplianceService(db_path)

    def test_create_destination(self, compliance_service, sample_student):
        dest = compliance_service.create_destination(
            student_id=sample_student["id"],
            destination_type="university",
            institution_name="Oxford University",
            course_title="Computer Science",
            contact_made=1,
        )
        assert dest["destination_type"] == "university"
        assert dest["institution_name"] == "Oxford University"

    def test_list_destinations_all(self, compliance_service, sample_student):
        compliance_service.create_destination(
            student_id=sample_student["id"],
            destination_type="apprenticeship",
            institution_name="Tech Corp",
        )
        destinations = compliance_service.list_destinations()
        assert len(destinations) >= 1

    def test_list_destinations_by_type(self, compliance_service, sample_student):
        compliance_service.create_destination(
            student_id=sample_student["id"],
            destination_type="university",
        )
        unis = compliance_service.list_destinations(destination_type="university")
        assert all(d["destination_type"] == "university" for d in unis)

    def test_list_destinations_contact_made(self, compliance_service, sample_student):
        compliance_service.create_destination(
            student_id=sample_student["id"],
            destination_type="university",
            contact_made=1,
        )
        contacted = compliance_service.list_destinations(contact_made=1)
        assert all(d["contact_made"] == 1 for d in contacted)

    def test_update_destination(self, compliance_service, sample_student):
        dest = compliance_service.create_destination(
            student_id=sample_student["id"],
            destination_type="unknown",
        )
        updated = compliance_service.update_destination(
            dest["id"],
            destination_type="employment",
            institution_name="Local Business",
            contact_made=1,
        )
        assert updated["destination_type"] == "employment"
        assert updated["contact_made"] == 1

    def test_update_destination_no_valid_fields(self, compliance_service, sample_student):
        dest = compliance_service.create_destination(
            student_id=sample_student["id"],
            destination_type="university",
        )
        with pytest.raises(ComplianceError, match="No valid fields"):
            compliance_service.update_destination(dest["id"], bad_field="nope")
