"""Tests for StaffDirectoryService."""
import pytest


class TestAddEntry:
    def test_add_entry_basic(self, staff_directory_service):
        entry = staff_directory_service.add_entry(
            first_name="Jane", last_name="Smith",
        )
        assert entry["first_name"] == "Jane"
        assert entry["last_name"] == "Smith"
        assert entry["role"] == "Teacher"
        assert entry["title"] == "Mr"

    def test_add_entry_full_details(self, staff_directory_service):
        entry = staff_directory_service.add_entry(
            first_name="Alice", last_name="Brown",
            title="Dr", role="Head of Department",
            department="Science", email="alice.brown@school.local",
            phone_ext="2345", room="Lab 1",
            subjects="Chemistry, Physics",
            responsibilities="KS4 Science Lead",
        )
        assert entry["title"] == "Dr"
        assert entry["department"] == "Science"
        assert entry["role"] == "Head of Department"
        assert entry["email"] == "alice.brown@school.local"
        assert entry["subjects"] == "Chemistry, Physics"


class TestListStaff:
    def test_list_staff_returns_entries(self, staff_directory_service):
        staff_directory_service.add_entry(first_name="A", last_name="One", department="Maths")
        staff_directory_service.add_entry(first_name="B", last_name="Two", department="English")
        result = staff_directory_service.list_staff()
        names = [s["first_name"] for s in result]
        assert "A" in names
        assert "B" in names

    def test_list_staff_filter_by_department(self, staff_directory_service):
        staff_directory_service.add_entry(first_name="A", last_name="One", department="Maths")
        staff_directory_service.add_entry(first_name="B", last_name="Two", department="English")
        maths = staff_directory_service.list_staff(department="Maths")
        assert all(s["department"] == "Maths" for s in maths)
        assert len(maths) >= 1


class TestGetDepartments:
    def test_get_departments_returns_unique(self, staff_directory_service):
        staff_directory_service.add_entry(first_name="A", last_name="One", department="Maths")
        staff_directory_service.add_entry(first_name="B", last_name="Two", department="English")
        staff_directory_service.add_entry(first_name="C", last_name="Three", department="Maths")
        depts = staff_directory_service.get_departments()
        assert "Maths" in depts
        assert "English" in depts
        assert depts.count("Maths") == 1  # unique


class TestDeleteEntry:
    def test_delete_entry_removes_it(self, staff_directory_service):
        entry = staff_directory_service.add_entry(
            first_name="X", last_name="Delete", department="PE",
        )
        staff_directory_service.delete_entry(entry["id"])
        remaining = staff_directory_service.list_staff(department="PE")
        ids = [s["id"] for s in remaining]
        assert entry["id"] not in ids
