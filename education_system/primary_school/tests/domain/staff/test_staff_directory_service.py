"""Tests for the StaffDirectoryService in the Primary School system."""

import pytest


class TestListAll:
    """Tests for listing all active staff."""

    def test_list_all_empty_db(self, staff_directory_service):
        """Listing staff on an empty database returns an empty list."""
        assert staff_directory_service.list_all() == []

    def test_list_all_returns_active_staff(self, staff_directory_service, sample_staff, hr_service):
        """Only active staff are returned by list_all."""
        results = staff_directory_service.list_all()
        assert len(results) >= 1
        ids = [s["staff_id"] for s in results]
        assert sample_staff["staff_id"] in ids

    def test_list_all_excludes_inactive(self, staff_directory_service, hr_service):
        """Staff marked as inactive are excluded from list_all."""
        s = hr_service.create_staff(first_name="Gone", last_name="Away", role="Teacher")
        hr_service.update_staff(s["staff_id"], status="Inactive")
        results = staff_directory_service.list_all()
        ids = [r["staff_id"] for r in results]
        assert s["staff_id"] not in ids

    def test_list_all_with_search(self, staff_directory_service, sample_staff):
        """The search parameter filters by name or role."""
        results = staff_directory_service.list_all(search="Alice")
        assert len(results) >= 1
        assert results[0]["first_name"] == "Alice"

    def test_list_all_search_no_match(self, staff_directory_service, sample_staff):
        """A search that matches nothing returns an empty list."""
        results = staff_directory_service.list_all(search="Nonexistent")
        assert results == []


class TestGetByRole:
    """Tests for filtering staff by role."""

    def test_get_by_role_returns_matching(self, staff_directory_service, hr_service):
        """Only staff with the specified role are returned."""
        hr_service.create_staff(first_name="A", last_name="B", role="Teacher")
        hr_service.create_staff(first_name="C", last_name="D", role="TA")
        teachers = staff_directory_service.get_by_role("Teacher")
        assert all(s["role"] == "Teacher" for s in teachers)

    def test_get_by_role_empty_result(self, staff_directory_service, sample_staff):
        """Querying a role with no staff returns an empty list."""
        results = staff_directory_service.get_by_role("Headteacher")
        assert results == []


class TestGetClassTeachers:
    """Tests for retrieving class teachers."""

    def test_get_class_teachers_none_assigned(self, staff_directory_service, sample_staff):
        """When no staff have class_teacher_of set, returns empty list."""
        results = staff_directory_service.get_class_teachers()
        assert results == []

    def test_get_class_teachers_returns_assigned(self, staff_directory_service, hr_service):
        """Staff with class_teacher_of set are returned."""
        s = hr_service.create_staff(
            first_name="Emma", last_name="Lead",
            role="Teacher", class_teacher_of="Year 2",
        )
        results = staff_directory_service.get_class_teachers()
        assert len(results) == 1
        assert results[0]["class_teacher_of"] == "Year 2"

    def test_class_teachers_excludes_non_class_staff(self, staff_directory_service, hr_service):
        """Staff without class_teacher_of are excluded."""
        hr_service.create_staff(first_name="A", last_name="B", role="Teacher",
                                class_teacher_of="Year 1")
        hr_service.create_staff(first_name="C", last_name="D", role="TA")
        results = staff_directory_service.get_class_teachers()
        assert len(results) == 1
        assert results[0]["first_name"] == "A"
