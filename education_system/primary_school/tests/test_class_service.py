"""Tests for ClassService in the Primary School Management System."""

import pytest

from education_system.primary_school.core.exceptions import ClassError


class TestCreateClass:
    """Tests for creating classes."""

    def test_create_class_minimal(self, class_service):
        """Creating a class with required fields only should succeed."""
        result = class_service.create_class(
            class_name="RA",
            year_group="Reception",
        )
        assert result["class_name"] == "RA"
        assert result["year_group"] == "Reception"

    def test_create_class_full_details(self, class_service):
        """Creating a class with all optional fields should succeed."""
        result = class_service.create_class(
            class_name="3B",
            year_group="Year 3",
            room="Room 12",
            capacity=28,
        )
        fetched = class_service.get_class("3B")
        assert fetched is not None
        assert fetched["year_group"] == "Year 3"
        assert fetched["room"] == "Room 12"
        assert fetched["capacity"] == 28

    def test_create_class_duplicate_raises(self, class_service, sample_class):
        """Creating a class with a duplicate name should raise ClassError."""
        with pytest.raises(ClassError):
            class_service.create_class(
                class_name="1A",
                year_group="Year 1",
            )

    def test_create_class_empty_name_raises(self, class_service):
        """Empty class name should raise ClassError."""
        with pytest.raises(ClassError):
            class_service.create_class(
                class_name="",
                year_group="Year 1",
            )

    def test_create_class_whitespace_name_raises(self, class_service):
        """Whitespace-only class name should raise ClassError."""
        with pytest.raises(ClassError):
            class_service.create_class(
                class_name="   ",
                year_group="Year 1",
            )

    def test_create_class_missing_year_group_raises(self, class_service):
        """Missing year group should raise ClassError."""
        with pytest.raises(ClassError):
            class_service.create_class(
                class_name="1C",
                year_group=None,
            )

    def test_create_multiple_classes_per_year(self, class_service):
        """Multiple classes can exist for the same year group."""
        class_service.create_class("2A", "Year 2")
        class_service.create_class("2B", "Year 2")
        class_service.create_class("2C", "Year 2")
        classes = class_service.list_classes(year_group="Year 2")
        assert len(classes) == 3

    def test_create_all_year_groups(self, class_service):
        """Should be able to create classes for every year group."""
        year_groups = [
            "Reception", "Year 1", "Year 2", "Year 3",
            "Year 4", "Year 5", "Year 6",
        ]
        for i, yg in enumerate(year_groups):
            class_service.create_class(f"C{i}", yg)
        all_classes = class_service.list_classes()
        assert len(all_classes) == 7


class TestGetClass:
    """Tests for retrieving individual classes."""

    def test_get_existing_class(self, class_service, sample_class):
        """Getting an existing class should return all fields."""
        cls = class_service.get_class("1A")
        assert cls is not None
        assert cls["class_name"] == "1A"
        assert cls["year_group"] == "Year 1"
        assert cls["room"] == "Room 3"
        assert cls["capacity"] == 30

    def test_get_nonexistent_class(self, class_service):
        """Getting a non-existent class should return None."""
        result = class_service.get_class("NOPE")
        assert result is None


class TestListClasses:
    """Tests for listing classes."""

    def test_list_all_classes(self, class_service):
        """Listing all classes should return every entry."""
        class_service.create_class("RA", "Reception")
        class_service.create_class("1A", "Year 1")
        class_service.create_class("2A", "Year 2")
        classes = class_service.list_classes()
        assert len(classes) == 3

    def test_list_by_year_group(self, class_service):
        """Filtering by year group should return only matching classes."""
        class_service.create_class("RA", "Reception")
        class_service.create_class("RB", "Reception")
        class_service.create_class("1A", "Year 1")
        reception = class_service.list_classes(year_group="Reception")
        assert len(reception) == 2
        for cls in reception:
            assert cls["year_group"] == "Reception"

    def test_list_ordered_by_year_and_name(self, class_service):
        """Classes should be ordered by year group then class name."""
        class_service.create_class("3B", "Year 3")
        class_service.create_class("1A", "Year 1")
        class_service.create_class("3A", "Year 3")
        classes = class_service.list_classes()
        names = [c["class_name"] for c in classes]
        assert names == ["1A", "3A", "3B"]

    def test_list_empty_database(self, class_service):
        """Listing from an empty database should return an empty list."""
        classes = class_service.list_classes()
        assert classes == []


class TestUpdateClass:
    """Tests for updating classes."""

    def test_update_room(self, class_service, sample_class):
        """Updating the room should persist."""
        updated = class_service.update_class("1A", room="Room 7")
        assert updated["room"] == "Room 7"

    def test_update_capacity(self, class_service, sample_class):
        """Updating the capacity should persist."""
        updated = class_service.update_class("1A", capacity=25)
        assert updated["capacity"] == 25

    def test_update_year_group(self, class_service, sample_class):
        """Updating the year group should persist."""
        updated = class_service.update_class("1A", year_group="Year 2")
        assert updated["year_group"] == "Year 2"

    def test_update_no_valid_fields(self, class_service, sample_class):
        """Updating with no valid fields should return None."""
        result = class_service.update_class("1A", invalid="test")
        assert result is None

    def test_update_disallowed_field_ignored(self, class_service, sample_class):
        """Fields not in the allowed set should be ignored."""
        updated = class_service.update_class(
            "1A", room="Room 9", created_at="2020-01-01",
        )
        # created_at is not in the allowed set; room is
        assert updated["room"] == "Room 9"
        assert updated["class_name"] == "1A"


class TestDeleteClass:
    """Tests for deleting classes."""

    def test_delete_existing_class(self, class_service, sample_class):
        """Deleting an existing class should return True."""
        deleted = class_service.delete_class("1A")
        assert deleted is True
        assert class_service.get_class("1A") is None

    def test_delete_nonexistent_class(self, class_service):
        """Deleting a non-existent class should return False."""
        deleted = class_service.delete_class("NOPE")
        assert deleted is False


class TestClassPupils:
    """Tests for getting pupils in a class."""

    def test_get_class_pupils(self, class_service, pupil_service, sample_class):
        """Getting pupils in a class should return pupils assigned to it."""
        pupil_service.create_pupil("Alice", "Adams", "Year 1", class_name="1A")
        pupil_service.create_pupil("Ben", "Baker", "Year 1", class_name="1A")
        pupil_service.create_pupil("Charlie", "Clark", "Year 1", class_name="1B")

        pupils = class_service.get_class_pupils("1A")
        assert len(pupils) == 2
        names = {p["first_name"] for p in pupils}
        assert names == {"Alice", "Ben"}

    def test_get_class_pupils_ordered_by_name(self, class_service, pupil_service,
                                                sample_class):
        """Pupils should be ordered by last name then first name."""
        pupil_service.create_pupil("Zara", "Adams", "Year 1", class_name="1A")
        pupil_service.create_pupil("Alice", "Adams", "Year 1", class_name="1A")
        pupil_service.create_pupil("Ben", "Baker", "Year 1", class_name="1A")

        pupils = class_service.get_class_pupils("1A")
        names = [(p["last_name"], p["first_name"]) for p in pupils]
        assert names == [("Adams", "Alice"), ("Adams", "Zara"), ("Baker", "Ben")]

    def test_get_class_pupils_empty_class(self, class_service, sample_class):
        """Getting pupils from a class with no pupils should return empty list."""
        pupils = class_service.get_class_pupils("1A")
        assert pupils == []
