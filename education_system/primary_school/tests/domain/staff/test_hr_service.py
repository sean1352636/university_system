"""Tests for the HRService in the Primary School system."""

import pytest


class TestCreateStaff:
    """Tests for creating staff records."""

    def test_create_staff_returns_dict_with_id(self, hr_service):
        """Creating a staff member returns a dict containing staff_id."""
        result = hr_service.create_staff(
            first_name="Bob", last_name="Green",
            email="bob.green@school.local", role="Teacher",
            department="Year 3",
        )
        assert isinstance(result, dict)
        assert result["staff_id"].startswith("STF")

    def test_auto_generated_ids_increment(self, hr_service):
        """Successive staff IDs increment in STF0001 format."""
        r1 = hr_service.create_staff(first_name="A", last_name="One", role="Teacher")
        r2 = hr_service.create_staff(first_name="B", last_name="Two", role="TA")
        num1 = int(r1["staff_id"].replace("STF", ""))
        num2 = int(r2["staff_id"].replace("STF", ""))
        assert num2 == num1 + 1

    def test_create_staff_with_all_optional_fields(self, hr_service):
        """Optional kwargs (start_date, qualifications, etc.) are persisted."""
        result = hr_service.create_staff(
            first_name="Claire", last_name="Davies",
            email="claire@school.local", role="Teacher",
            department="Year 5", phone="07700900123",
            start_date="2025-09-01", dbs_check_date="2025-08-01",
            qualifications="PGCE, QTS",
        )
        staff = hr_service.get_staff(result["staff_id"])
        assert staff["phone"] == "07700900123"
        assert staff["start_date"] == "2025-09-01"
        assert staff["qualifications"] == "PGCE, QTS"


class TestGetStaff:
    """Tests for retrieving a single staff record."""

    def test_get_existing_staff(self, hr_service, sample_staff):
        """Retrieving an existing staff member returns a full dict."""
        staff = hr_service.get_staff(sample_staff["staff_id"])
        assert staff is not None
        assert staff["first_name"] == "Alice"
        assert staff["last_name"] == "Teacher"

    def test_get_nonexistent_staff(self, hr_service):
        """Retrieving a non-existent ID returns None."""
        assert hr_service.get_staff("STF9999") is None


class TestListStaff:
    """Tests for listing staff with filters."""

    def test_list_staff_empty_db(self, hr_service):
        """Listing staff on an empty database returns an empty list."""
        results = hr_service.list_staff()
        assert results == []

    def test_list_staff_returns_created(self, hr_service, sample_staff):
        """Created staff appear in the list."""
        results = hr_service.list_staff()
        assert len(results) >= 1
        ids = [s["staff_id"] for s in results]
        assert sample_staff["staff_id"] in ids

    def test_list_staff_filter_by_role(self, hr_service):
        """Filtering by role returns only matching staff."""
        hr_service.create_staff(first_name="X", last_name="Y", role="Teacher")
        hr_service.create_staff(first_name="Z", last_name="W", role="TA")
        teachers = hr_service.list_staff(role="Teacher")
        assert all(s["role"] == "Teacher" for s in teachers)


class TestUpdateStaff:
    """Tests for updating staff records."""

    def test_update_staff_field(self, hr_service, sample_staff):
        """Updating a field persists the change."""
        updated = hr_service.update_staff(
            sample_staff["staff_id"], department="Year 4",
        )
        assert updated["department"] == "Year 4"

    def test_update_with_no_valid_fields(self, hr_service, sample_staff):
        """Passing no recognised fields returns None."""
        result = hr_service.update_staff(sample_staff["staff_id"], bogus="val")
        assert result is None


class TestDeleteStaff:
    """Tests for deleting staff records."""

    def test_delete_existing_staff(self, hr_service, sample_staff):
        """Deleting an existing staff member returns True and removes them."""
        assert hr_service.delete_staff(sample_staff["staff_id"]) is True
        assert hr_service.get_staff(sample_staff["staff_id"]) is None

    def test_delete_nonexistent_staff(self, hr_service):
        """Deleting a non-existent staff ID returns False."""
        assert hr_service.delete_staff("STF9999") is False


class TestLeave:
    """Tests for leave recording and approval."""

    def test_record_leave_returns_id(self, hr_service, sample_staff):
        """Recording leave returns an integer leave ID."""
        leave_id = hr_service.record_leave(
            staff_id=sample_staff["staff_id"],
            leave_type="Annual",
            start_date="2026-04-07",
            end_date="2026-04-11",
            reason="Holiday",
        )
        assert isinstance(leave_id, int)
        assert leave_id > 0

    def test_get_leave_by_staff(self, hr_service, sample_staff):
        """Leave records can be filtered by staff_id."""
        sid = sample_staff["staff_id"]
        hr_service.record_leave(sid, "Sick", "2026-05-01", "2026-05-02")
        records = hr_service.get_leave(staff_id=sid)
        assert len(records) == 1
        assert records[0]["leave_type"] == "Sick"
        assert records[0]["status"] == "Pending"

    def test_get_leave_empty_db(self, hr_service):
        """Querying leave on an empty database returns an empty list."""
        assert hr_service.get_leave() == []

    def test_approve_leave(self, hr_service, sample_staff):
        """Approving a leave request updates the status."""
        sid = sample_staff["staff_id"]
        leave_id = hr_service.record_leave(sid, "Annual", "2026-06-01", "2026-06-05")
        result = hr_service.approve_leave(leave_id, approved_by="STF0099")
        assert result is True
        records = hr_service.get_leave(staff_id=sid, status="Approved")
        assert len(records) == 1
        assert records[0]["approved_by"] == "STF0099"
