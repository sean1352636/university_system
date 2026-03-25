"""Tests for AdmissionsService."""
import pytest


class TestAdmissions:
    def test_create_application(self, admissions_service):
        app = admissions_service.create_application(
            first_name="New", last_name="Applicant", year_group="7",
            parent_name="Mrs Applicant", parent_email="parent@test.com",
        )
        assert app["applicant_first_name"] == "New"
        assert app["status"] == "received"

    def test_list_applications(self, admissions_service):
        admissions_service.create_application("A", "One", "7", "P1")
        admissions_service.create_application("B", "Two", "8", "P2")
        result = admissions_service.list_applications()
        assert len(result) >= 2

    def test_list_applications_filter_year_group(self, admissions_service):
        admissions_service.create_application("A", "One", "7", "P1")
        admissions_service.create_application("B", "Two", "8", "P2")
        result = admissions_service.list_applications(year_group="7")
        assert all(a["year_group_applying"] == "7" for a in result)

    def test_update_status(self, admissions_service):
        app = admissions_service.create_application("A", "One", "7", "P1")
        admissions_service.update_status(app["id"], "accepted", decision_by="Head")
        result = admissions_service.list_applications(status="accepted")
        assert any(a["id"] == app["id"] for a in result)

    def test_delete_application(self, admissions_service):
        app = admissions_service.create_application("A", "One", "7", "P1")
        admissions_service.delete_application(app["id"])
        result = admissions_service.list_applications()
        assert all(a["id"] != app["id"] for a in result)

    def test_status_summary(self, admissions_service):
        admissions_service.create_application("A", "One", "7", "P1")
        admissions_service.create_application("B", "Two", "8", "P2")
        summary = admissions_service.status_summary()
        assert isinstance(summary, (list, dict))
