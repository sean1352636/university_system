"""Tests for SubjectService in the Primary School Management System."""

import pytest

from education_system.primary_school.core.exceptions import SubjectError


class TestCreateSubject:
    """Tests for creating subjects."""

    def test_create_core_subject(self, subject_service):
        """Creating a core subject should succeed and return the code and title."""
        result = subject_service.create_subject(
            subject_code="SCI",
            title="Science",
            description="Primary science curriculum",
            is_core=1,
        )
        assert result["subject_code"] == "SCI"
        assert result["title"] == "Science"

    def test_create_foundation_subject(self, subject_service):
        """Creating a non-core (foundation) subject should succeed."""
        result = subject_service.create_subject(
            subject_code="ART",
            title="Art and Design",
            is_core=0,
        )
        assert result["subject_code"] == "ART"
        assert result["title"] == "Art and Design"

    def test_create_subject_with_key_stage(self, subject_service):
        """Creating a subject linked to a key stage should persist."""
        subject_service.create_subject(
            subject_code="PHO",
            title="Phonics",
            key_stage="KS1",
        )
        fetched = subject_service.get_subject("PHO")
        assert fetched["key_stage"] == "KS1"

    def test_create_duplicate_code_raises(self, subject_service, sample_subject):
        """Creating a subject with a duplicate code should raise SubjectError."""
        with pytest.raises(SubjectError):
            subject_service.create_subject(
                subject_code="ENG",
                title="English Duplicate",
            )

    def test_create_subject_empty_code_raises(self, subject_service):
        """Empty subject code should raise SubjectError."""
        with pytest.raises(SubjectError):
            subject_service.create_subject(
                subject_code="",
                title="Test Subject",
            )

    def test_create_subject_empty_title_raises(self, subject_service):
        """Empty title should raise SubjectError."""
        with pytest.raises(SubjectError):
            subject_service.create_subject(
                subject_code="TST",
                title="",
            )

    def test_create_subject_whitespace_code_raises(self, subject_service):
        """Whitespace-only subject code should raise SubjectError."""
        with pytest.raises(SubjectError):
            subject_service.create_subject(
                subject_code="   ",
                title="Test",
            )


class TestGetSubject:
    """Tests for retrieving individual subjects."""

    def test_get_existing_subject(self, subject_service, sample_subject):
        """Getting an existing subject should return all fields."""
        subj = subject_service.get_subject("ENG")
        assert subj is not None
        assert subj["title"] == "English"
        assert subj["is_core"] == 1
        assert subj["description"] == "English language and literacy"

    def test_get_nonexistent_subject(self, subject_service):
        """Getting a non-existent subject should return None."""
        result = subject_service.get_subject("NOPE")
        assert result is None


class TestListSubjects:
    """Tests for listing subjects."""

    def test_list_all_subjects(self, subject_service, sample_subject, sample_subject_maths):
        """Listing all subjects should return all entries."""
        subjects = subject_service.list_subjects()
        assert len(subjects) == 2

    def test_list_subjects_by_core(self, subject_service, sample_subject):
        """Filtering by is_core should return only matching subjects."""
        subject_service.create_subject("MUS", "Music", is_core=0)
        core_subjects = subject_service.list_subjects(is_core=1)
        non_core = subject_service.list_subjects(is_core=0)
        assert len(core_subjects) == 1
        assert core_subjects[0]["subject_code"] == "ENG"
        assert len(non_core) == 1
        assert non_core[0]["subject_code"] == "MUS"

    def test_list_subjects_by_key_stage(self, subject_service):
        """Filtering by key_stage should return only matching subjects."""
        subject_service.create_subject("PHO", "Phonics", key_stage="KS1")
        subject_service.create_subject("HIS", "History", key_stage="KS2")
        ks1 = subject_service.list_subjects(key_stage="KS1")
        assert len(ks1) == 1
        assert ks1[0]["subject_code"] == "PHO"

    def test_list_subjects_ordered_by_title(self, subject_service):
        """Subjects should be ordered alphabetically by title."""
        subject_service.create_subject("SCI", "Science")
        subject_service.create_subject("ART", "Art")
        subject_service.create_subject("MAT", "Mathematics")
        subjects = subject_service.list_subjects()
        titles = [s["title"] for s in subjects]
        assert titles == sorted(titles)

    def test_list_empty_database(self, subject_service):
        """Listing from an empty database should return an empty list."""
        assert subject_service.list_subjects() == []


class TestUpdateSubject:
    """Tests for updating subjects."""

    def test_update_title(self, subject_service, sample_subject):
        """Updating the title should persist."""
        updated = subject_service.update_subject("ENG", title="English Language")
        assert updated["title"] == "English Language"

    def test_update_description(self, subject_service, sample_subject):
        """Updating the description should persist."""
        updated = subject_service.update_subject(
            "ENG", description="Updated description",
        )
        assert updated["description"] == "Updated description"

    def test_update_is_core(self, subject_service, sample_subject):
        """Should be able to toggle the is_core flag."""
        updated = subject_service.update_subject("ENG", is_core=0)
        assert updated["is_core"] == 0

    def test_update_no_valid_fields(self, subject_service, sample_subject):
        """Updating with no valid fields should return None."""
        result = subject_service.update_subject("ENG", invalid="test")
        assert result is None

    def test_update_key_stage(self, subject_service, sample_subject):
        """Should be able to set the key stage."""
        updated = subject_service.update_subject("ENG", key_stage="KS2")
        assert updated["key_stage"] == "KS2"


class TestDeleteSubject:
    """Tests for deleting subjects."""

    def test_delete_existing_subject(self, subject_service, sample_subject):
        """Deleting an existing subject should return True."""
        deleted = subject_service.delete_subject("ENG")
        assert deleted is True
        assert subject_service.get_subject("ENG") is None

    def test_delete_nonexistent_subject(self, subject_service):
        """Deleting a non-existent subject should return False."""
        deleted = subject_service.delete_subject("NOPE")
        assert deleted is False
