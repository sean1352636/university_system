"""Tests for hesa_export_service.py — HESA statutory return management.

Uses the autouse ``_isolate_db`` fixture: ``HESAExportService()`` builds its
tables (hesa_returns / hesa_field_mappings / hesa_submission_log) via
``transaction()`` against the isolated default DB.

NOTE: ``generate_xml_export`` is NOT exercised here — see the module-level
note at the bottom of this file for the source bug it hits.
"""

import pytest

from education_system.systems.university.domain.governance.compliance.hesa_export.services.hesa_export_service import (
    HESAExportService,
)


@pytest.fixture
def svc():
    return HESAExportService()


class TestReturns:
    def test_create_and_get_return(self, svc):
        rid = svc.create_return("2024/25", "Student", created_by="admin", notes="first draft")
        assert isinstance(rid, int) and rid > 0
        ret = svc.get_return(rid)
        assert ret["academic_year"] == "2024/25"
        assert ret["return_type"] == "Student"
        assert ret["status"] == "draft"
        assert ret["created_by"] == "admin"

    def test_get_missing_return(self, svc):
        assert svc.get_return(999999) is None

    def test_list_returns(self, svc):
        svc.create_return("2024/25", "Student")
        svc.create_return("2024/25", "Staff")
        assert len(svc.list_returns()) == 2

    def test_list_returns_filtered_by_status(self, svc):
        rid = svc.create_return("2024/25", "Student")
        svc.create_return("2024/25", "Staff")
        svc.update_return_status(rid, "submitted", performed_by="admin")
        submitted = svc.list_returns(status="submitted")
        assert len(submitted) == 1
        assert submitted[0]["id"] == rid

    def test_update_status_logs_and_sets_submitted_at(self, svc):
        rid = svc.create_return("2024/25", "Student")
        assert svc.update_return_status(rid, "submitted", performed_by="admin") is True
        ret = svc.get_return(rid)
        assert ret["status"] == "submitted"
        assert ret["submitted_at"] is not None
        log = svc.get_submission_log(rid)
        assert any("submitted" in row["action"] for row in log)


class TestFieldMappings:
    def test_add_and_get_mapping(self, svc):
        mid = svc.add_field_mapping("Student", "SID", "student_id", "uppercase")
        assert isinstance(mid, int) and mid > 0
        mappings = svc.get_field_mappings("Student")
        assert len(mappings) == 1
        assert mappings[0]["hesa_field"] == "SID"
        assert mappings[0]["local_field"] == "student_id"

    def test_get_all_mappings(self, svc):
        svc.add_field_mapping("Student", "SID", "student_id")
        svc.add_field_mapping("Staff", "STAFFID", "staff_id")
        assert len(svc.get_field_mappings()) == 2

    def test_get_mappings_empty(self, svc):
        assert svc.get_field_mappings("Nonexistent") == []


class TestSubmissionLog:
    def test_log_and_get(self, svc):
        rid = svc.create_return("2024/25", "Student")
        lid = svc.log_submission_action(rid, "validated", "no errors", "admin")
        assert isinstance(lid, int) and lid > 0
        log = svc.get_submission_log(rid)
        assert len(log) == 1
        assert log[0]["action"] == "validated"
        assert log[0]["details"] == "no errors"

    def test_get_log_empty(self, svc):
        rid = svc.create_return("2024/25", "Student")
        assert svc.get_submission_log(rid) == []


class TestStatistics:
    def test_return_statistics(self, svc):
        r1 = svc.create_return("2024/25", "Student")
        svc.create_return("2024/25", "Staff")
        svc.update_return_status(r1, "submitted", "admin")
        stats = svc.get_return_statistics()
        assert stats["total"] == 2
        assert stats["by_status"].get("submitted") == 1
        assert stats["by_status"].get("draft") == 1

    def test_statistics_empty(self, svc):
        stats = svc.get_return_statistics()
        assert stats["total"] == 0
        assert stats["by_status"] == {}


# ---------------------------------------------------------------------------
# SOURCE BUG (not tested): HESAExportService.generate_xml_export() calls
# ET.Element / ET.SubElement where ET is ``defusedxml.ElementTree``.
# defusedxml.ElementTree does not export Element/SubElement (only parsing
# helpers + tostring), so the method raises AttributeError. Left untested
# rather than editing source.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
