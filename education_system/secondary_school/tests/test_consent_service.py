"""Tests for ConsentService."""
import pytest

from education_system.secondary_school.modules.domain.student_life.consent.services.consent_service import ConsentService


@pytest.fixture
def consent_service(db_path):
    return ConsentService(db_path)


class TestConsentRecords:
    def test_add_record(self, consent_service, sample_student):
        rec = consent_service.add_record(
            student_id=sample_student["id"],
            consent_type="photo_internal",
            granted=True, granted_by="Parent",
            granted_date="2026-01-10",
        )
        assert rec["student_id"] == sample_student["id"]
        assert rec["consent_type"] == "photo_internal"
        assert rec["granted"] == 1

    def test_list_records(self, consent_service, sample_student):
        consent_service.add_record(sample_student["id"], "photo_internal", granted=True)
        consent_service.add_record(sample_student["id"], "data_sharing", granted=False)
        result = consent_service.list_records()
        assert len(result) == 2

    def test_list_records_filter_by_student(self, consent_service, sample_student, sample_student_ks4):
        consent_service.add_record(sample_student["id"], "photo_internal")
        consent_service.add_record(sample_student_ks4["id"], "photo_internal")
        result = consent_service.list_records(student_id=sample_student["id"])
        assert len(result) == 1

    def test_list_records_filter_by_type(self, consent_service, sample_student):
        consent_service.add_record(sample_student["id"], "photo_internal")
        consent_service.add_record(sample_student["id"], "data_sharing")
        result = consent_service.list_records(consent_type="data_sharing")
        assert len(result) == 1
        assert result[0]["consent_type"] == "data_sharing"

    def test_toggle_granted(self, consent_service, sample_student):
        rec = consent_service.add_record(sample_student["id"], "biometric", granted=False)
        assert rec["granted"] == 0
        consent_service.toggle_granted(rec["id"], True)
        records = consent_service.list_records(student_id=sample_student["id"])
        assert records[0]["granted"] == 1

    def test_delete_record(self, consent_service, sample_student):
        rec = consent_service.add_record(sample_student["id"], "photo_external")
        consent_service.delete_record(rec["id"])
        result = consent_service.list_records(student_id=sample_student["id"])
        assert len(result) == 0

    def test_summary_by_type(self, consent_service, sample_student, sample_student_ks4):
        consent_service.add_record(sample_student["id"], "photo_internal", granted=True)
        consent_service.add_record(sample_student_ks4["id"], "photo_internal", granted=False)
        consent_service.add_record(sample_student["id"], "data_sharing", granted=True)
        summary = consent_service.summary_by_type()
        assert len(summary) == 2
        photo = [s for s in summary if s["consent_type"] == "photo_internal"][0]
        assert photo["total"] == 2
        assert photo["granted_count"] == 1
