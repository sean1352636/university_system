"""Tests for the AdmissionsService in the Primary School system."""

import pytest


class TestCreateApplication:
    """Tests for creating admission applications."""

    def test_create_application_returns_dict(self, admissions_service):
        """Creating an application returns a dict with id and status."""
        result = admissions_service.create_application(
            first_name="Emma",
            last_name="Brown",
            year_group_applied="Reception",
            date_of_birth="2021-03-15",
            parent_name="Jane Brown",
            parent_email="jane.brown@example.com",
            parent_phone="07700900100",
            address="10 Oak Lane",
            notes="Sibling already enrolled",
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["status"] == "Pending"
        assert result["first_name"] == "Emma"

    def test_create_application_persists(self, admissions_service):
        """Created application can be retrieved by ID."""
        result = admissions_service.create_application(
            first_name="Liam",
            last_name="Taylor",
            year_group_applied="Year 1",
        )
        fetched = admissions_service.get_application(result["id"])
        assert fetched is not None
        assert fetched["first_name"] == "Liam"
        assert fetched["year_group_applied"] == "Year 1"

    def test_create_multiple_applications(self, admissions_service):
        """Multiple applications receive distinct IDs."""
        a1 = admissions_service.create_application(
            first_name="A", last_name="One", year_group_applied="Reception",
        )
        a2 = admissions_service.create_application(
            first_name="B", last_name="Two", year_group_applied="Year 2",
        )
        assert a1["id"] != a2["id"]


class TestGetApplication:
    """Tests for retrieving applications."""

    def test_get_nonexistent_returns_none(self, admissions_service):
        """Fetching a non-existent ID returns None."""
        assert admissions_service.get_application(99999) is None

    def test_get_application_has_all_fields(self, admissions_service):
        """Retrieved application contains stored optional fields."""
        admissions_service.create_application(
            first_name="Sophie",
            last_name="White",
            year_group_applied="Year 3",
            parent_email="sophie.parent@example.com",
            address="5 Elm Street",
        )
        apps = admissions_service.list_applications()
        assert len(apps) == 1
        assert apps[0]["parent_email"] == "sophie.parent@example.com"
        assert apps[0]["address"] == "5 Elm Street"


class TestListApplications:
    """Tests for listing applications."""

    def test_list_empty_db(self, admissions_service):
        """Listing on an empty database returns an empty list."""
        assert admissions_service.list_applications() == []

    def test_list_filter_by_year_group(self, admissions_service):
        """Filtering by year group returns only matching applications."""
        admissions_service.create_application(
            first_name="X", last_name="Y", year_group_applied="Reception",
        )
        admissions_service.create_application(
            first_name="A", last_name="B", year_group_applied="Year 4",
        )
        results = admissions_service.list_applications(year_group="Reception")
        assert len(results) == 1
        assert results[0]["year_group_applied"] == "Reception"


class TestUpdateApplication:
    """Tests for updating applications."""

    def test_update_application_fields(self, admissions_service):
        """Updating fields persists the changes."""
        app = admissions_service.create_application(
            first_name="Old", last_name="Name", year_group_applied="Year 1",
        )
        updated = admissions_service.update_application(
            app["id"], first_name="New", notes="Updated note",
        )
        assert updated["first_name"] == "New"
        assert updated["notes"] == "Updated note"

    def test_update_with_no_valid_fields(self, admissions_service):
        """Passing unrecognised fields returns None."""
        app = admissions_service.create_application(
            first_name="Test", last_name="User", year_group_applied="Year 2",
        )
        result = admissions_service.update_application(app["id"], bogus="value")
        assert result is None


class TestApproveReject:
    """Tests for approve and reject workflows."""

    def test_approve_application(self, admissions_service):
        """Approving sets status to Approved."""
        app = admissions_service.create_application(
            first_name="App", last_name="Roved", year_group_applied="Year 1",
        )
        result = admissions_service.approve_application(app["id"])
        assert result["status"] == "Approved"

    def test_reject_application(self, admissions_service):
        """Rejecting sets status to Rejected."""
        app = admissions_service.create_application(
            first_name="Rej", last_name="Ected", year_group_applied="Year 3",
        )
        result = admissions_service.reject_application(app["id"])
        assert result["status"] == "Rejected"

    def test_filter_by_status(self, admissions_service):
        """list_applications can filter by status after approval."""
        a1 = admissions_service.create_application(
            first_name="P", last_name="One", year_group_applied="Year 1",
        )
        a2 = admissions_service.create_application(
            first_name="P", last_name="Two", year_group_applied="Year 1",
        )
        admissions_service.approve_application(a1["id"])
        approved = admissions_service.list_applications(status="Approved")
        assert len(approved) == 1
        assert approved[0]["id"] == a1["id"]
