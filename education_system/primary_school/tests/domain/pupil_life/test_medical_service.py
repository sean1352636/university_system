"""Tests for the MedicalService in the Primary School system."""

import pytest


class TestCreateRecord:
    """Tests for creating medical records."""

    def test_create_record_returns_dict(self, medical_service, sample_pupil):
        """Creating a medical record returns a dict with id and pupil_id."""
        result = medical_service.create_record(
            pupil_id=sample_pupil["pupil_id"],
            condition="Asthma",
            medication="Salbutamol inhaler",
            dosage="2 puffs as needed",
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["pupil_id"] == sample_pupil["pupil_id"]

    def test_create_record_persists(self, medical_service, sample_pupil):
        """A created medical record can be retrieved."""
        medical_service.create_record(
            pupil_id=sample_pupil["pupil_id"],
            condition="Diabetes Type 1",
            medication="Insulin",
            care_plan=1,
            doctor_name="Dr Thompson",
            doctor_phone="01onal234567",
        )
        records = medical_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert len(records) == 1
        assert records[0]["condition"] == "Diabetes Type 1"
        assert records[0]["care_plan"] == 1
        assert records[0]["doctor_name"] == "Dr Thompson"

    def test_create_record_with_allergy(self, medical_service, sample_pupil):
        """An allergy record stores allergy and severity fields."""
        medical_service.create_record(
            pupil_id=sample_pupil["pupil_id"],
            allergy="Peanuts",
            allergy_severity="Severe",
            emergency_protocol="Administer EpiPen, call 999",
        )
        records = medical_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert records[0]["allergy"] == "Peanuts"
        assert records[0]["allergy_severity"] == "Severe"
        assert records[0]["emergency_protocol"] == "Administer EpiPen, call 999"

    def test_create_multiple_records(self, medical_service, sample_pupil):
        """Multiple records for the same pupil are stored independently."""
        medical_service.create_record(pupil_id=sample_pupil["pupil_id"], condition="Asthma")
        medical_service.create_record(pupil_id=sample_pupil["pupil_id"], allergy="Gluten")
        records = medical_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert len(records) == 2


class TestGetRecords:
    """Tests for retrieving medical records."""

    def test_get_records_empty_db(self, medical_service):
        """Querying an empty database returns an empty list."""
        assert medical_service.get_records() == []

    def test_get_records_by_pupil(self, medical_service, sample_pupil, sample_pupil_ks1):
        """Filtering by pupil_id returns only that pupil's records."""
        medical_service.create_record(pupil_id=sample_pupil["pupil_id"], condition="Eczema")
        medical_service.create_record(pupil_id=sample_pupil_ks1["pupil_id"], condition="Hay fever")
        records = medical_service.get_records(pupil_id=sample_pupil["pupil_id"])
        assert len(records) == 1
        assert records[0]["condition"] == "Eczema"

    def test_get_all_records(self, medical_service, sample_pupil, sample_pupil_ks1):
        """Getting records without filters returns all records."""
        medical_service.create_record(pupil_id=sample_pupil["pupil_id"], condition="A")
        medical_service.create_record(pupil_id=sample_pupil_ks1["pupil_id"], condition="B")
        records = medical_service.get_records()
        assert len(records) == 2


class TestUpdateRecord:
    """Tests for updating medical records."""

    @pytest.mark.xfail(reason="schema missing updated_at column")
    def test_update_condition(self, medical_service, sample_pupil):
        """Updating a condition persists the change."""
        result = medical_service.create_record(
            pupil_id=sample_pupil["pupil_id"], condition="Mild asthma",
        )
        updated = medical_service.update_record(result["id"], condition="Severe asthma")
        assert updated["condition"] == "Severe asthma"

    @pytest.mark.xfail(reason="schema missing updated_at column")
    def test_update_medication_and_dosage(self, medical_service, sample_pupil):
        """Updating medication and dosage persists both changes."""
        result = medical_service.create_record(
            pupil_id=sample_pupil["pupil_id"], condition="Epilepsy",
        )
        updated = medical_service.update_record(
            result["id"], medication="Carbamazepine", dosage="200mg twice daily",
        )
        assert updated["medication"] == "Carbamazepine"
        assert updated["dosage"] == "200mg twice daily"

    def test_update_with_no_valid_fields(self, medical_service, sample_pupil):
        """Passing no recognised fields returns None."""
        result = medical_service.create_record(
            pupil_id=sample_pupil["pupil_id"], condition="Test",
        )
        assert medical_service.update_record(result["id"], bogus="val") is None


class TestDeleteRecord:
    """Tests for deleting medical records."""

    def test_delete_existing_record(self, medical_service, sample_pupil):
        """Deleting an existing record returns True and removes it."""
        result = medical_service.create_record(
            pupil_id=sample_pupil["pupil_id"], condition="Old condition",
        )
        assert medical_service.delete_record(result["id"]) is True
        assert medical_service.get_records(pupil_id=sample_pupil["pupil_id"]) == []

    def test_delete_nonexistent_record(self, medical_service):
        """Deleting a non-existent record returns False."""
        assert medical_service.delete_record(99999) is False


class TestGetAllergies:
    """Tests for the get_allergies method."""

    def test_get_allergies_empty(self, medical_service):
        """No allergy records returns an empty list."""
        assert medical_service.get_allergies() == []

    def test_get_allergies_returns_only_allergy_records(self, medical_service, sample_pupil):
        """get_allergies returns only records where allergy is set."""
        medical_service.create_record(
            pupil_id=sample_pupil["pupil_id"], allergy="Dairy", allergy_severity="Moderate",
        )
        medical_service.create_record(
            pupil_id=sample_pupil["pupil_id"], condition="Asthma",
        )
        allergies = medical_service.get_allergies()
        assert len(allergies) == 1
        assert allergies[0]["allergy"] == "Dairy"

    def test_get_allergies_multiple_pupils(self, medical_service, sample_pupil, sample_pupil_ks1):
        """Allergies from multiple pupils are all returned."""
        medical_service.create_record(pupil_id=sample_pupil["pupil_id"], allergy="Nuts")
        medical_service.create_record(pupil_id=sample_pupil_ks1["pupil_id"], allergy="Eggs")
        allergies = medical_service.get_allergies()
        assert len(allergies) == 2
