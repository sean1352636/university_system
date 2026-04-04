"""Tests for HRService."""
import pytest
from education_system.secondary_school.core.exceptions import HRError


class TestCreateStaff:
    def test_create_staff_basic(self, hr_service):
        s = hr_service.create_staff(first_name="Jane", last_name="Smith", job_title="Teacher")
        assert s["first_name"] == "Jane"
        assert s["last_name"] == "Smith"
        assert s["status"] == "active"
        assert s["contract_type"] == "permanent"

    def test_create_staff_full_details(self, hr_service):
        s = hr_service.create_staff(
            first_name="John", last_name="Doe", title="Dr",
            email="john.doe@school.local", department="Science",
            job_title="Head of Science", contract_type="permanent",
            salary=45000, start_date="2020-09-01",
            dbs_check_date="2020-08-01", dbs_certificate="DBS123456",
        )
        assert s["title"] == "Dr"
        assert s["department"] == "Science"
        assert s["salary"] == 45000


class TestListStaff:
    def test_list_staff_empty(self, hr_service):
        # May have seeded staff, but filter for unlikely dept
        result = hr_service.list_staff(department="Nonexistent")
        assert len(result) == 0

    def test_list_staff_returns_created(self, hr_service):
        hr_service.create_staff(first_name="A", last_name="One", department="Maths")
        hr_service.create_staff(first_name="B", last_name="Two", department="Science")
        result = hr_service.list_staff()
        names = [s["first_name"] for s in result]
        assert "A" in names and "B" in names

    def test_list_staff_filter_department(self, hr_service):
        hr_service.create_staff(first_name="A", last_name="One", department="Maths")
        hr_service.create_staff(first_name="B", last_name="Two", department="Science")
        maths = hr_service.list_staff(department="Maths")
        assert all(s["department"] == "Maths" for s in maths)


class TestStaffCRUD:
    def test_get_staff(self, hr_service):
        s = hr_service.create_staff(first_name="A", last_name="Get")
        found = hr_service.get_staff(s["id"])
        assert found is not None
        assert found["first_name"] == "A"

    def test_update_staff(self, hr_service):
        s = hr_service.create_staff(first_name="A", last_name="Update")
        updated = hr_service.update_staff(s["id"], department="PE")
        assert updated["department"] == "PE"

    def test_delete_staff(self, hr_service):
        s = hr_service.create_staff(first_name="A", last_name="Delete")
        hr_service.delete_staff(s["id"])
        assert hr_service.get_staff(s["id"]) is None


class TestLeave:
    def test_request_leave(self, hr_service):
        s = hr_service.create_staff(first_name="A", last_name="Leave")
        leave = hr_service.request_leave(s["id"], "annual", "2026-04-01", "2026-04-05", days=5, reason="Holiday")
        assert leave["leave_type"] == "annual"
        assert leave["status"] == "pending"

    def test_approve_leave(self, hr_service):
        s = hr_service.create_staff(first_name="A", last_name="Approve")
        leave = hr_service.request_leave(s["id"], "sick", "2026-04-01", "2026-04-02")
        hr_service.approve_leave(leave["id"], approved_by="Head Teacher")
        leaves = hr_service.list_leave(s["id"])
        approved = [l for l in leaves if l["id"] == leave["id"]]
        assert approved[0]["status"] == "approved"

    def test_reject_leave(self, hr_service):
        s = hr_service.create_staff(first_name="A", last_name="Reject")
        leave = hr_service.request_leave(s["id"], "annual", "2026-04-01", "2026-04-03")
        hr_service.reject_leave(leave["id"])
        leaves = hr_service.list_leave(s["id"])
        rejected = [l for l in leaves if l["id"] == leave["id"]]
        assert rejected[0]["status"] == "rejected"

    def test_list_leave_filter_status(self, hr_service):
        s = hr_service.create_staff(first_name="A", last_name="Filter")
        hr_service.request_leave(s["id"], "annual", "2026-04-01", "2026-04-02")
        hr_service.request_leave(s["id"], "sick", "2026-04-10", "2026-04-11")
        pending = hr_service.list_leave(status="pending")
        assert len(pending) >= 2
