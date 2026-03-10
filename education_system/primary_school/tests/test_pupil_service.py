"""Tests for PupilService in the Primary School Management System."""

import pytest

from education_system.primary_school.core.exceptions import PupilError, ValidationError


class TestCreatePupil:
    """Tests for creating pupils."""

    def test_create_pupil_minimal(self, pupil_service):
        """Creating a pupil with required fields only should succeed."""
        result = pupil_service.create_pupil(
            first_name="Emma",
            last_name="Wilson",
            year_group="Reception",
        )
        assert result["pupil_id"].startswith("PRI")
        assert result["first_name"] == "Emma"
        assert result["last_name"] == "Wilson"
        assert result["year_group"] == "Reception"

    def test_create_pupil_full_details(self, pupil_service):
        """Creating a pupil with all optional fields should succeed."""
        result = pupil_service.create_pupil(
            first_name="James",
            last_name="Brown",
            year_group="Year 3",
            preferred_name="Jimmy",
            date_of_birth="2017-04-12",
            gender="Male",
            class_name="3B",
            ethnicity="White British",
            first_language="English",
            eal=0,
            pupil_premium=1,
            free_school_meals=1,
            sen_status="SEN Support",
            parent1_name="Jane Brown",
            parent1_email="jane.brown@example.com",
            parent1_phone="07700900010",
            parent1_relationship="Mother",
            address="10 School Lane",
        )
        assert result["pupil_id"].startswith("PRI")
        assert result["year_group"] == "Year 3"

    def test_create_pupil_auto_id_increment(self, pupil_service):
        """Each new pupil should get an incrementing PRI ID."""
        p1 = pupil_service.create_pupil("Alice", "Green", "Year 1")
        p2 = pupil_service.create_pupil("Bob", "Green", "Year 2")
        id1 = int(p1["pupil_id"].replace("PRI", ""))
        id2 = int(p2["pupil_id"].replace("PRI", ""))
        assert id2 == id1 + 1

    def test_create_pupil_assigns_key_stage(self, pupil_service):
        """Pupil key_stage should be set based on year group."""
        p = pupil_service.create_pupil("Test", "EYFS", "Reception")
        full = pupil_service.get_pupil(p["pupil_id"])
        assert full["key_stage"] == "EYFS"

        p2 = pupil_service.create_pupil("Test", "KS1", "Year 2")
        full2 = pupil_service.get_pupil(p2["pupil_id"])
        assert full2["key_stage"] == "KS1"

        p3 = pupil_service.create_pupil("Test", "KS2", "Year 6")
        full3 = pupil_service.get_pupil(p3["pupil_id"])
        assert full3["key_stage"] == "KS2"

    def test_create_pupil_empty_first_name_raises(self, pupil_service):
        """Empty first name should raise ValidationError."""
        with pytest.raises(ValidationError):
            pupil_service.create_pupil("", "Smith", "Year 1")

    def test_create_pupil_empty_last_name_raises(self, pupil_service):
        """Empty last name should raise ValidationError."""
        with pytest.raises(ValidationError):
            pupil_service.create_pupil("John", "", "Year 1")

    def test_create_pupil_invalid_year_group_raises(self, pupil_service):
        """Invalid year group should raise ValidationError."""
        with pytest.raises(ValidationError):
            pupil_service.create_pupil("John", "Smith", "Year 8")

    def test_create_pupil_whitespace_name_raises(self, pupil_service):
        """Whitespace-only names should raise ValidationError."""
        with pytest.raises(ValidationError):
            pupil_service.create_pupil("   ", "Smith", "Year 1")


class TestGetPupil:
    """Tests for retrieving individual pupils."""

    def test_get_existing_pupil(self, pupil_service, sample_pupil):
        """Getting an existing pupil by ID should return all fields."""
        pupil = pupil_service.get_pupil(sample_pupil["pupil_id"])
        assert pupil is not None
        assert pupil["first_name"] == "Oliver"
        assert pupil["last_name"] == "Smith"
        assert pupil["year_group"] == "Reception"
        assert pupil["key_stage"] == "EYFS"
        assert pupil["parent1_name"] == "Sarah Smith"
        assert pupil["status"] == "Active"

    def test_get_nonexistent_pupil(self, pupil_service):
        """Getting a non-existent pupil should return None."""
        result = pupil_service.get_pupil("PRI9999")
        assert result is None


class TestListPupils:
    """Tests for listing and searching pupils."""

    def test_list_all_active_pupils(self, pupil_service, sample_pupil, sample_pupil_ks1):
        """Listing active pupils should return all active entries."""
        pupils = pupil_service.list_pupils()
        assert len(pupils) == 2

    def test_list_pupils_by_year_group(self, pupil_service, sample_pupil, sample_pupil_ks1):
        """Filtering by year group should return only matching pupils."""
        pupils = pupil_service.list_pupils(year_group="Reception")
        assert len(pupils) == 1
        assert pupils[0]["first_name"] == "Oliver"

    def test_list_pupils_by_class_name(self, pupil_service):
        """Filtering by class name should return only matching pupils."""
        pupil_service.create_pupil("Lily", "Patel", "Year 3", class_name="3A")
        pupil_service.create_pupil("Noah", "Patel", "Year 3", class_name="3B")
        pupils = pupil_service.list_pupils(class_name="3A")
        assert len(pupils) == 1
        assert pupils[0]["first_name"] == "Lily"

    def test_search_pupils_by_name(self, pupil_service, sample_pupil, sample_pupil_ks1):
        """Searching by name should match partial strings."""
        results = pupil_service.list_pupils(search="Oliver")
        assert len(results) == 1
        assert results[0]["last_name"] == "Smith"

    def test_search_pupils_by_id(self, pupil_service, sample_pupil):
        """Searching by pupil ID substring should work."""
        results = pupil_service.list_pupils(search="PRI")
        assert len(results) >= 1

    def test_list_empty_database(self, pupil_service):
        """Listing from an empty database should return an empty list."""
        pupils = pupil_service.list_pupils()
        assert pupils == []


class TestUpdatePupil:
    """Tests for updating pupil records."""

    def test_update_basic_fields(self, pupil_service, sample_pupil):
        """Updating allowed fields should persist the changes."""
        updated = pupil_service.update_pupil(
            sample_pupil["pupil_id"],
            preferred_name="Ollie",
            class_name="RA",
        )
        assert updated["preferred_name"] == "Ollie"
        assert updated["class_name"] == "RA"

    def test_update_year_group_changes_key_stage(self, pupil_service, sample_pupil):
        """Changing year group should also update key stage."""
        updated = pupil_service.update_pupil(
            sample_pupil["pupil_id"],
            year_group="Year 4",
        )
        assert updated["year_group"] == "Year 4"
        assert updated["key_stage"] == "KS2"

    def test_update_pupil_premium_flag(self, pupil_service, sample_pupil):
        """Should be able to set the pupil premium flag."""
        updated = pupil_service.update_pupil(
            sample_pupil["pupil_id"],
            pupil_premium=1,
            free_school_meals=1,
        )
        assert updated["pupil_premium"] == 1
        assert updated["free_school_meals"] == 1

    def test_update_status_to_left(self, pupil_service, sample_pupil):
        """Should be able to mark a pupil as Left."""
        updated = pupil_service.update_pupil(
            sample_pupil["pupil_id"],
            status="Left",
            leaving_date="2026-07-20",
        )
        assert updated["status"] == "Left"
        assert updated["leaving_date"] == "2026-07-20"

    def test_update_with_no_valid_fields(self, pupil_service, sample_pupil):
        """Updating with no valid fields should return None."""
        result = pupil_service.update_pupil(
            sample_pupil["pupil_id"],
            invalid_field="test",
        )
        assert result is None

    def test_update_disallowed_field_ignored(self, pupil_service, sample_pupil):
        """Fields not in the allowed set should be silently ignored."""
        pid = sample_pupil["pupil_id"]
        updated = pupil_service.update_pupil(
            pid,
            first_name="Changed",
            created_at="2020-01-01",  # not in allowed set
        )
        # first_name is allowed, created_at is not
        assert updated["first_name"] == "Changed"
        assert updated["pupil_id"] == pid


class TestDeletePupil:
    """Tests for deleting pupils."""

    def test_delete_existing_pupil(self, pupil_service, sample_pupil):
        """Deleting an existing pupil should return True."""
        deleted = pupil_service.delete_pupil(sample_pupil["pupil_id"])
        assert deleted is True

        # Verify the pupil is gone
        result = pupil_service.get_pupil(sample_pupil["pupil_id"])
        assert result is None

    def test_delete_nonexistent_pupil(self, pupil_service):
        """Deleting a non-existent pupil should return False."""
        deleted = pupil_service.delete_pupil("PRI9999")
        assert deleted is False

    def test_delete_cascades_related_records(self, pupil_service, assessment_service,
                                              sample_pupil, sample_subject):
        """Deleting a pupil should also remove related assessment records."""
        pid = sample_pupil["pupil_id"]
        assessment_service.record_assessment(
            pid, sample_subject["subject_code"], "Expected",
        )
        pupil_service.delete_pupil(pid)
        records = assessment_service.get_assessments(pupil_id=pid)
        assert records == []


class TestCountPupils:
    """Tests for counting pupils."""

    def test_count_all_active(self, pupil_service, sample_pupil, sample_pupil_ks1):
        """Count should reflect the number of active pupils."""
        assert pupil_service.count_pupils() == 2

    def test_count_by_year_group(self, pupil_service, sample_pupil, sample_pupil_ks1):
        """Count with year group filter should be accurate."""
        assert pupil_service.count_pupils(year_group="Reception") == 1
        assert pupil_service.count_pupils(year_group="Year 1") == 1
        assert pupil_service.count_pupils(year_group="Year 6") == 0

    def test_count_empty_database(self, pupil_service):
        """Count on an empty database should return zero."""
        assert pupil_service.count_pupils() == 0
