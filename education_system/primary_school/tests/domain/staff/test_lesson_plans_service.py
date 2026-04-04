"""Tests for the LessonPlansService in the Primary School system."""

import pytest


class TestCreate:
    """Tests for creating lesson plan records."""

    def test_create_returns_id(self, lesson_plans_service, sample_staff):
        """Creating a lesson plan returns a positive integer ID."""
        record_id = lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"],
            subject="Mathematics",
            class_name="2A",
            lesson_date="2026-04-07",
            topic="Place value to 100",
            objectives="Understand place value to 100",
            activities="Base-10 blocks, number line work",
            resources="Base-10 set, whiteboards",
            assessment="Can partition two-digit numbers",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_minimal_fields(self, lesson_plans_service, sample_staff):
        """A lesson plan with only required fields can be created."""
        record_id = lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"],
            topic="Fractions introduction",
        )
        assert record_id > 0

    def test_create_multiple_plans(self, lesson_plans_service, sample_staff):
        """Multiple plans for the same teacher are stored independently."""
        id1 = lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"],
            topic="Addition", subject="Maths", lesson_date="2026-04-07",
        )
        id2 = lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"],
            topic="Story writing", subject="English", lesson_date="2026-04-07",
        )
        assert id1 != id2


class TestListAll:
    """Tests for listing lesson plan records."""

    def test_list_all_empty_db(self, lesson_plans_service):
        """Querying an empty database returns an empty list."""
        assert lesson_plans_service.list_all() == []

    def test_list_all_returns_created(self, lesson_plans_service, sample_staff):
        """Created plans appear in list_all."""
        lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"],
            subject="Science", class_name="3B",
            topic="Plant growth",
            lesson_date="2026-04-08",
        )
        results = lesson_plans_service.list_all()
        assert len(results) == 1
        assert results[0]["subject"] == "Science"

    def test_list_all_filter_by_teacher(self, lesson_plans_service, sample_staff, hr_service):
        """Filtering by teacher_id returns only that teacher's plans."""
        s2 = hr_service.create_staff(first_name="R", last_name="S", role="Teacher")
        lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"], topic="Art shapes",
        )
        lesson_plans_service.create(
            teacher_id=s2["staff_id"], topic="Music rhythm",
        )
        results = lesson_plans_service.list_all(teacher_id=sample_staff["staff_id"])
        assert len(results) == 1
        assert results[0]["topic"] == "Art shapes"

    def test_list_all_filter_by_subject(self, lesson_plans_service, sample_staff):
        """Filtering by subject returns only matching plans."""
        lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"],
            topic="Counting", subject="Maths",
        )
        lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"],
            topic="Phonics", subject="English",
        )
        results = lesson_plans_service.list_all(subject="Maths")
        assert len(results) == 1
        assert results[0]["topic"] == "Counting"


class TestGet:
    """Tests for retrieving a single lesson plan."""

    def test_get_existing(self, lesson_plans_service, sample_staff):
        """Retrieving an existing plan returns a dict with all fields."""
        rid = lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"],
            subject="PE", class_name="4C",
            lesson_date="2026-04-09",
            topic="Throwing and catching",
            objectives="Develop throwing and catching",
            activities="Paired drills, small-sided games",
            resources="Foam balls, cones",
            assessment="Consistent catch from 5m",
        )
        record = lesson_plans_service.get(rid)
        assert record is not None
        assert record["subject"] == "PE"
        assert record["objectives"] == "Develop throwing and catching"
        assert record["resources"] == "Foam balls, cones"

    def test_get_nonexistent(self, lesson_plans_service):
        """Retrieving a non-existent ID returns None."""
        assert lesson_plans_service.get(99999) is None


class TestUpdate:
    """Tests for updating lesson plan records."""

    def test_update_field(self, lesson_plans_service, sample_staff):
        """Updating a field persists the change."""
        rid = lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"],
            topic="Old topic", objectives="Old objectives",
        )
        result = lesson_plans_service.update(rid, objectives="Revised objectives")
        assert result is True
        record = lesson_plans_service.get(rid)
        assert record["objectives"] == "Revised objectives"

    def test_update_no_fields_returns_false(self, lesson_plans_service, sample_staff):
        """Passing no fields returns False."""
        rid = lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"], topic="DT project",
        )
        result = lesson_plans_service.update(rid)
        assert result is False


class TestDelete:
    """Tests for deleting lesson plan records."""

    def test_delete_existing(self, lesson_plans_service, sample_staff):
        """Deleting an existing record returns True and removes it."""
        rid = lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"], topic="Geography rivers",
        )
        assert lesson_plans_service.delete(rid) is True
        assert lesson_plans_service.get(rid) is None

    def test_delete_does_not_affect_others(self, lesson_plans_service, sample_staff):
        """Deleting one plan leaves other plans intact."""
        id1 = lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"], topic="RE festivals",
        )
        id2 = lesson_plans_service.create(
            teacher_id=sample_staff["staff_id"], topic="PSHE emotions",
        )
        lesson_plans_service.delete(id2)
        assert lesson_plans_service.get(id1) is not None
        assert lesson_plans_service.get(id2) is None
