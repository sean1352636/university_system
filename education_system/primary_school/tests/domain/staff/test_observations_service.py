"""Tests for the ObservationsService in the Primary School system."""

import pytest


class TestCreate:
    """Tests for creating lesson observation records."""

    def test_create_returns_id(self, observations_service, sample_staff):
        """Creating an observation returns a positive integer ID."""
        record_id = observations_service.create(
            staff_id=sample_staff["staff_id"],
            observer_id="STF0099",
            observation_date="2026-03-10",
            subject="Mathematics",
            class_name="2A",
            grade="Good",
            strengths="Strong use of manipulatives",
            areas_for_improvement="Extend higher-ability pupils",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_minimal_fields(self, observations_service, sample_staff):
        """An observation with only staff_id and observation_date can be created."""
        record_id = observations_service.create(
            staff_id=sample_staff["staff_id"],
            observation_date="2026-03-12",
        )
        assert record_id > 0

    def test_create_multiple_observations(self, observations_service, sample_staff):
        """Multiple observations for the same staff are stored independently."""
        id1 = observations_service.create(
            staff_id=sample_staff["staff_id"], observation_date="2026-01-15",
        )
        id2 = observations_service.create(
            staff_id=sample_staff["staff_id"], observation_date="2026-03-15",
        )
        assert id1 != id2


class TestListAll:
    """Tests for listing observation records."""

    def test_list_all_empty_db(self, observations_service):
        """Querying an empty database returns an empty list."""
        assert observations_service.list_all() == []

    def test_list_all_returns_created(self, observations_service, sample_staff):
        """Created observations appear in list_all."""
        observations_service.create(
            staff_id=sample_staff["staff_id"],
            observation_date="2026-03-10",
            subject="English",
            grade="Outstanding",
        )
        results = observations_service.list_all()
        assert len(results) == 1
        assert results[0]["subject"] == "English"

    def test_list_all_filter_by_staff(self, observations_service, sample_staff, hr_service):
        """Filtering by staff_id returns only that staff's observations."""
        s2 = hr_service.create_staff(first_name="P", last_name="Q", role="Teacher")
        observations_service.create(
            staff_id=sample_staff["staff_id"], observation_date="2026-01-01",
        )
        observations_service.create(
            staff_id=s2["staff_id"], observation_date="2026-02-01",
        )
        results = observations_service.list_all(staff_id=sample_staff["staff_id"])
        assert len(results) == 1


class TestGet:
    """Tests for retrieving a single observation."""

    def test_get_existing(self, observations_service, sample_staff):
        """Retrieving an existing observation returns a dict with all fields."""
        rid = observations_service.create(
            staff_id=sample_staff["staff_id"],
            observer_id="STF0099",
            observation_date="2026-03-10",
            subject="Science",
            class_name="4B",
            grade="Good",
            strengths="Engaging experiments",
            areas_for_improvement="More pupil-led inquiry",
        )
        record = observations_service.get(rid)
        assert record is not None
        assert record["subject"] == "Science"
        assert record["strengths"] == "Engaging experiments"

    def test_get_nonexistent(self, observations_service):
        """Retrieving a non-existent ID returns None."""
        assert observations_service.get(99999) is None


class TestUpdate:
    """Tests for updating observation records."""

    def test_update_field(self, observations_service, sample_staff):
        """Updating a field persists the change."""
        rid = observations_service.create(
            staff_id=sample_staff["staff_id"],
            observation_date="2026-03-10",
            grade="Requires Improvement",
        )
        result = observations_service.update(rid, grade="Good")
        assert result is True
        record = observations_service.get(rid)
        assert record["grade"] == "Good"

    def test_update_no_fields_returns_false(self, observations_service, sample_staff):
        """Passing no fields returns False."""
        rid = observations_service.create(
            staff_id=sample_staff["staff_id"],
            observation_date="2026-03-10",
        )
        result = observations_service.update(rid)
        assert result is False


class TestDelete:
    """Tests for deleting observation records."""

    def test_delete_existing(self, observations_service, sample_staff):
        """Deleting an existing record returns True and removes it."""
        rid = observations_service.create(
            staff_id=sample_staff["staff_id"],
            observation_date="2026-03-10",
        )
        assert observations_service.delete(rid) is True
        assert observations_service.get(rid) is None

    def test_delete_does_not_affect_others(self, observations_service, sample_staff):
        """Deleting one record leaves other records intact."""
        id1 = observations_service.create(
            staff_id=sample_staff["staff_id"], observation_date="2026-01-10",
        )
        id2 = observations_service.create(
            staff_id=sample_staff["staff_id"], observation_date="2026-03-10",
        )
        observations_service.delete(id2)
        assert observations_service.get(id1) is not None
        assert observations_service.get(id2) is None
