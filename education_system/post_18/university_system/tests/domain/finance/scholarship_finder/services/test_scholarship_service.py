"""Tests for scholarship_service.py — scholarship discovery, profiles,
applications and the document vault.

All managers use ``get_connection()`` / ``transaction()`` against the default
DB path (isolated per-test by the autouse ``_isolate_db`` fixture). The
``_tables`` fixture rebuilds the scholarship tables in the isolated DB.
"""

import pytest
from datetime import datetime, timedelta

from education_system.post_18.university_system.modules.domain.finance.scholarship_finder.services.scholarship_service import (
    ScholarshipDatabase,
    StudentProfileManager,
    ApplicationManager,
    DocumentVaultManager,
)
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.infrastructure.database.db import get_connection


# student_ids referenced by the profile/application/vault tests. These tables
# carry FK(student_id) -> students(student_id), so the rows must exist.
_SEED_STUDENTS = [f"STU{n}" for n in (100, 101, 102, 200, 201, 202, 203, 204, 205, 300, 301, 302, 303)]


@pytest.fixture(autouse=True)
def _tables():
    ScholarshipDatabase.create_tables()
    conn = get_connection()
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO students (student_id, first_name, last_name) VALUES (?, 'Test', 'Student')",
            [(sid,) for sid in _SEED_STUDENTS],
        )
        conn.commit()
    finally:
        conn.close()
    yield


def _future(days):
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def _make_scholarship(deadline_days=60, **kw):
    return ScholarshipDatabase.add_scholarship(
        kw.pop("name", "Merit Award"),
        kw.pop("organization", "ACME Foundation"),
        kw.pop("organization_type", "foundation"),
        kw.pop("award_amount_min", 5000.0),
        kw.pop("description", "For high achievers"),
        _future(deadline_days),
        **kw,
    )


class TestScholarshipDatabase:
    def test_add_scholarship_returns_id(self):
        sid = _make_scholarship()
        assert isinstance(sid, int) and sid > 0

    def test_get_scholarship_details(self):
        sid = _make_scholarship(name="STEM Grant", award_amount_min=8000.0)
        details = ScholarshipDatabase.get_scholarship_details(sid)
        assert details is not None
        assert details["scholarship_name"] == "STEM Grant"
        assert details["award_amount_min"] == 8000.0
        assert "application_stats" in details

    def test_get_scholarship_details_missing(self):
        assert ScholarshipDatabase.get_scholarship_details(999999) is None

    def test_search_scholarships_all(self):
        _make_scholarship(name="A")
        _make_scholarship(name="B")
        results = ScholarshipDatabase.search_scholarships()
        assert len(results) == 2

    def test_search_scholarships_filter_org_type(self):
        _make_scholarship(name="Gov", organization_type="government")
        _make_scholarship(name="Priv", organization_type="private")
        gov = ScholarshipDatabase.search_scholarships(filters={"organization_type": "government"})
        assert len(gov) == 1
        assert gov[0]["scholarship_name"] == "Gov"

    def test_search_scholarships_min_award(self):
        _make_scholarship(name="Small", award_amount_min=1000.0)
        _make_scholarship(name="Big", award_amount_min=10000.0)
        big = ScholarshipDatabase.search_scholarships(filters={"min_award": 5000})
        assert [r["scholarship_name"] for r in big] == ["Big"]

    def test_search_sort_by_amount(self):
        _make_scholarship(name="Low", award_amount_min=1000.0)
        _make_scholarship(name="High", award_amount_min=9000.0)
        results = ScholarshipDatabase.search_scholarships(sort_by="amount")
        assert results[0]["scholarship_name"] == "High"


class TestStudentProfileManager:
    def test_create_profile(self):
        pid = StudentProfileManager.create_or_update_profile(
            "STU100", citizenship_status="citizen",
            state_residency="CA", financial_need_level="high",
        )
        assert isinstance(pid, int) and pid > 0

    def test_get_profile(self):
        StudentProfileManager.create_or_update_profile(
            "STU101", citizenship_status="citizen", financial_need_level="moderate",
        )
        profile = StudentProfileManager.get_student_profile("STU101")
        assert profile is not None
        assert profile["citizenship_status"] == "citizen"
        assert profile["profile_completeness"] > 0

    def test_get_profile_missing(self):
        assert StudentProfileManager.get_student_profile("NOBODY") is None

    def test_update_existing_profile(self):
        StudentProfileManager.create_or_update_profile("STU102", citizenship_status="citizen")
        StudentProfileManager.create_or_update_profile("STU102", state_residency="NY")
        profile = StudentProfileManager.get_student_profile("STU102")
        assert profile["state_residency"] == "NY"
        # still a single profile row (unique student_id)
        assert profile["student_id"] == "STU102"


class TestApplicationManager:
    def test_start_application(self):
        sid = _make_scholarship(deadline_days=90)
        aid = ApplicationManager.start_application("STU200", sid, match_score=75.0)
        assert isinstance(aid, int) and aid > 0

    def test_start_application_unknown_scholarship(self):
        with pytest.raises(ValidationError):
            ApplicationManager.start_application("STU200", 999999)

    def test_get_student_applications(self):
        sid = _make_scholarship()
        ApplicationManager.start_application("STU201", sid)
        apps = ApplicationManager.get_student_applications("STU201")
        assert len(apps) == 1
        assert apps[0]["student_id"] == "STU201"
        assert apps[0]["scholarship_name"]  # joined column present

    def test_update_application_progress(self):
        sid = _make_scholarship()
        aid = ApplicationManager.start_application("STU202", sid)
        assert ApplicationManager.update_application_progress(
            aid, essay_completed=1, transcript_uploaded=1, documents_completed=1,
        ) is True
        apps = ApplicationManager.get_student_applications("STU202")
        assert apps[0]["application_progress"] == 100

    def test_update_application_progress_no_fields(self):
        sid = _make_scholarship()
        aid = ApplicationManager.start_application("STU203", sid)
        assert ApplicationManager.update_application_progress(aid, bogus="x") is False

    def test_submit_incomplete_application_raises(self):
        sid = _make_scholarship()
        aid = ApplicationManager.start_application("STU204", sid)
        with pytest.raises(ValidationError):
            ApplicationManager.submit_application(aid)

    def test_submit_complete_application(self):
        sid = _make_scholarship()
        aid = ApplicationManager.start_application("STU205", sid)
        ApplicationManager.update_application_progress(
            aid, essay_completed=1, transcript_uploaded=1, documents_completed=1,
        )
        assert ApplicationManager.submit_application(aid) is True
        apps = ApplicationManager.get_student_applications("STU205", status="submitted")
        assert len(apps) == 1


class TestDocumentVaultManager:
    def test_upload_document(self):
        did = DocumentVaultManager.upload_document(
            "STU300", "Personal Essay", "essay", "/vault/essay.pdf",
            file_size=2048, file_format="pdf",
        )
        assert isinstance(did, int) and did > 0

    def test_get_student_documents(self):
        DocumentVaultManager.upload_document("STU301", "Resume", "resume", "/v/r.pdf")
        DocumentVaultManager.upload_document("STU301", "Transcript", "transcript", "/v/t.pdf")
        docs = DocumentVaultManager.get_student_documents("STU301")
        assert len(docs) == 2

    def test_get_student_documents_by_type(self):
        DocumentVaultManager.upload_document("STU302", "Resume", "resume", "/v/r.pdf")
        DocumentVaultManager.upload_document("STU302", "Essay", "essay", "/v/e.pdf")
        essays = DocumentVaultManager.get_student_documents("STU302", document_type="essay")
        assert len(essays) == 1
        assert essays[0]["document_type"] == "essay"

    def test_track_document_usage(self):
        did = DocumentVaultManager.upload_document("STU303", "R", "resume", "/v/r.pdf")
        assert DocumentVaultManager.track_document_usage(did) is True
        docs = DocumentVaultManager.get_student_documents("STU303")
        assert docs[0]["usage_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
