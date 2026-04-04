"""Tests for the ClassGroupService in the Primary School system."""

import pytest


class TestGetClassInfo:
    """Tests for retrieving class information."""

    def test_get_class_info(self, class_group_service, sample_class, class_service):
        """Getting class info returns the class details."""
        info = class_group_service.get_class_info("1A")
        assert info is not None
        assert info["class_name"] == "1A"
        assert info["year_group"] == "Year 1"
        assert info["room"] == "Room 3"

    def test_get_nonexistent_class(self, class_group_service):
        """Getting a non-existent class returns None."""
        assert class_group_service.get_class_info("99Z") is None


class TestAssignPupilToClass:
    """Tests for assigning pupils to classes."""

    def test_assign_pupil(self, class_group_service, sample_class, sample_pupil):
        """Assigning a pupil to a class returns True."""
        result = class_group_service.assign_pupil_to_class(sample_pupil["pupil_id"], "1A")
        assert result is True

    def test_assign_pupil_persists(self, class_group_service, sample_class, sample_pupil):
        """An assigned pupil appears in get_class_pupils."""
        class_group_service.assign_pupil_to_class(sample_pupil["pupil_id"], "1A")
        pupils = class_group_service.get_class_pupils("1A")
        assert len(pupils) == 1
        assert pupils[0]["pupil_id"] == sample_pupil["pupil_id"]

    def test_assign_multiple_pupils(self, class_group_service, sample_class,
                                     sample_pupil, sample_pupil_ks1):
        """Multiple pupils can be assigned to the same class."""
        class_group_service.assign_pupil_to_class(sample_pupil["pupil_id"], "1A")
        class_group_service.assign_pupil_to_class(sample_pupil_ks1["pupil_id"], "1A")
        pupils = class_group_service.get_class_pupils("1A")
        assert len(pupils) == 2


class TestGetClassPupils:
    """Tests for retrieving pupils in a class."""

    def test_get_class_pupils_empty(self, class_group_service, sample_class):
        """A class with no assigned pupils returns an empty list."""
        pupils = class_group_service.get_class_pupils("1A")
        assert pupils == []

    def test_get_class_pupils_ordered(self, class_group_service, sample_class,
                                       sample_pupil_ks1, sample_pupil):
        """Pupils are returned ordered by last_name, first_name."""
        class_group_service.assign_pupil_to_class(sample_pupil_ks1["pupil_id"], "1A")
        class_group_service.assign_pupil_to_class(sample_pupil["pupil_id"], "1A")
        pupils = class_group_service.get_class_pupils("1A")
        last_names = [p["last_name"] for p in pupils]
        assert last_names == sorted(last_names)


class TestRemovePupilFromClass:
    """Tests for removing pupils from classes."""

    def test_remove_pupil(self, class_group_service, sample_class, sample_pupil):
        """Removing a pupil from a class returns True."""
        class_group_service.assign_pupil_to_class(sample_pupil["pupil_id"], "1A")
        result = class_group_service.remove_pupil_from_class(sample_pupil["pupil_id"])
        assert result is True

    def test_remove_pupil_clears_class(self, class_group_service, sample_class, sample_pupil):
        """After removal, the pupil no longer appears in the class."""
        class_group_service.assign_pupil_to_class(sample_pupil["pupil_id"], "1A")
        class_group_service.remove_pupil_from_class(sample_pupil["pupil_id"])
        pupils = class_group_service.get_class_pupils("1A")
        assert len(pupils) == 0

    def test_remove_does_not_affect_others(self, class_group_service, sample_class,
                                            sample_pupil, sample_pupil_ks1):
        """Removing one pupil leaves others in the class."""
        class_group_service.assign_pupil_to_class(sample_pupil["pupil_id"], "1A")
        class_group_service.assign_pupil_to_class(sample_pupil_ks1["pupil_id"], "1A")
        class_group_service.remove_pupil_from_class(sample_pupil["pupil_id"])
        pupils = class_group_service.get_class_pupils("1A")
        assert len(pupils) == 1
        assert pupils[0]["pupil_id"] == sample_pupil_ks1["pupil_id"]


class TestListClassesWithCounts:
    """Tests for listing classes with pupil counts."""

    def test_list_empty_classes(self, class_group_service, sample_class):
        """A class with no pupils shows pupil_count of 0."""
        classes = class_group_service.list_classes_with_counts()
        assert len(classes) >= 1
        cls = next(c for c in classes if c["class_name"] == "1A")
        assert cls["pupil_count"] == 0

    def test_list_with_assigned_pupils(self, class_group_service, sample_class,
                                        sample_pupil, sample_pupil_ks1):
        """Classes show correct pupil counts after assignment."""
        class_group_service.assign_pupil_to_class(sample_pupil["pupil_id"], "1A")
        class_group_service.assign_pupil_to_class(sample_pupil_ks1["pupil_id"], "1A")
        classes = class_group_service.list_classes_with_counts()
        cls = next(c for c in classes if c["class_name"] == "1A")
        assert cls["pupil_count"] == 2
