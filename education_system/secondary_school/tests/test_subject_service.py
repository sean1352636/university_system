"""Comprehensive tests for SubjectService."""

import pytest
from education_system.secondary_school.core.exceptions import SubjectError, ValidationError


class TestCreateSubject:
    """Tests for creating subjects."""

    def test_create_subject_basic(self, subject_service):
        subject = subject_service.create_subject(
            subject_code="ENG01", title="English Literature",
            department="English", key_stage="KS4",
        )
        assert subject["subject_code"] == "ENG01"
        assert subject["title"] == "English Literature"
        assert subject["department"] == "English"
        assert subject["key_stage"] == "KS4"
        assert subject["status"] == "active"

    def test_create_subject_with_all_fields(self, subject_service):
        subject = subject_service.create_subject(
            subject_code="HIS01", title="History",
            description="GCSE History course",
            department="Humanities", key_stage="KS4",
            is_core=False, capacity=25,
            teacher="Ms Johnson", room="H102",
        )
        assert subject["description"] == "GCSE History course"
        assert subject["teacher"] == "Ms Johnson"
        assert subject["room"] == "H102"
        assert subject["capacity"] == 25
        assert subject["is_core"] == 0

    def test_create_subject_uppercases_code(self, subject_service):
        subject = subject_service.create_subject(
            subject_code="sci01", title="Biology",
        )
        assert subject["subject_code"] == "SCI01"

    def test_create_subject_mixed_case_code(self, subject_service):
        subject = subject_service.create_subject(
            subject_code="Geo01", title="Geography",
        )
        assert subject["subject_code"] == "GEO01"

    def test_create_subject_validates_empty_code(self, subject_service):
        with pytest.raises(ValidationError):
            subject_service.create_subject(subject_code="", title="Empty Code")

    def test_create_subject_validates_empty_title(self, subject_service):
        with pytest.raises(ValidationError):
            subject_service.create_subject(subject_code="TEST", title="")

    def test_create_subject_validates_whitespace_code(self, subject_service):
        with pytest.raises(ValidationError):
            subject_service.create_subject(subject_code="   ", title="Whitespace Code")

    def test_create_duplicate_subject_raises(self, subject_service, sample_subject):
        with pytest.raises(SubjectError):
            subject_service.create_subject(
                subject_code="MAT01", title="Duplicate Maths",
            )

    def test_create_subject_default_capacity(self, subject_service):
        subject = subject_service.create_subject(
            subject_code="ART01", title="Art",
        )
        assert subject["capacity"] == 30

    def test_create_subject_default_key_stage(self, subject_service):
        subject = subject_service.create_subject(
            subject_code="MUS01", title="Music",
        )
        assert subject["key_stage"] == "KS3"

    def test_create_subject_is_core_flag(self, subject_service):
        core = subject_service.create_subject(
            subject_code="MAT01", title="Maths", is_core=True,
        )
        non_core = subject_service.create_subject(
            subject_code="ART01", title="Art", is_core=False,
        )
        assert core["is_core"] == 1
        assert non_core["is_core"] == 0


class TestGetSubject:
    """Tests for retrieving subjects."""

    def test_get_subject_by_pk(self, subject_service, sample_subject):
        found = subject_service.get_subject(sample_subject["id"])
        assert found is not None
        assert found["title"] == "Mathematics"
        assert found["department"] == "Maths"

    def test_get_subject_by_code(self, subject_service, sample_subject):
        found = subject_service.get_subject_by_code("MAT01")
        assert found is not None
        assert found["department"] == "Maths"
        assert found["id"] == sample_subject["id"]

    def test_get_nonexistent_subject_returns_none(self, subject_service):
        assert subject_service.get_subject(9999) is None

    def test_get_nonexistent_code_returns_none(self, subject_service):
        assert subject_service.get_subject_by_code("NOPE99") is None

    def test_get_subject_returns_all_fields(self, subject_service, sample_subject):
        found = subject_service.get_subject(sample_subject["id"])
        expected_fields = ["id", "subject_code", "title", "department", "key_stage",
                           "is_core", "capacity", "status"]
        for field in expected_fields:
            assert field in found


class TestListSubjects:
    """Tests for listing and filtering subjects."""

    def test_list_subjects_empty(self, subject_service):
        subjects = subject_service.list_subjects()
        assert len(subjects) == 0

    def test_list_subjects_returns_all(self, subject_service):
        subject_service.create_subject(subject_code="ENG01", title="English")
        subject_service.create_subject(subject_code="SCI01", title="Science")
        subject_service.create_subject(subject_code="MAT01", title="Maths")
        subjects = subject_service.list_subjects()
        assert len(subjects) == 3

    def test_list_subjects_filter_key_stage(self, subject_service):
        subject_service.create_subject(subject_code="ENG01", title="English KS3", key_stage="KS3")
        subject_service.create_subject(subject_code="ENG02", title="English KS4", key_stage="KS4")
        ks3 = subject_service.list_subjects(key_stage="KS3")
        ks4 = subject_service.list_subjects(key_stage="KS4")
        assert len(ks3) == 1
        assert ks3[0]["key_stage"] == "KS3"
        assert len(ks4) == 1

    def test_list_subjects_filter_department(self, subject_service):
        subject_service.create_subject(subject_code="MAT01", title="Maths", department="Maths")
        subject_service.create_subject(subject_code="ENG01", title="English", department="English")
        subject_service.create_subject(subject_code="ENG02", title="English Lit", department="English")
        maths = subject_service.list_subjects(department="Maths")
        english = subject_service.list_subjects(department="English")
        assert len(maths) == 1
        assert len(english) == 2

    def test_list_subjects_search_by_title(self, subject_service):
        subject_service.create_subject(subject_code="MAT01", title="Mathematics")
        subject_service.create_subject(subject_code="ENG01", title="English")
        results = subject_service.list_subjects(search="Math")
        assert len(results) == 1
        assert results[0]["title"] == "Mathematics"

    def test_list_subjects_search_by_code(self, subject_service):
        subject_service.create_subject(subject_code="MAT01", title="Maths")
        subject_service.create_subject(subject_code="ENG01", title="English")
        results = subject_service.list_subjects(search="MAT")
        assert len(results) == 1

    def test_list_subjects_limit(self, subject_service):
        for i in range(5):
            subject_service.create_subject(subject_code=f"TST{i:02d}", title=f"Test {i}")
        results = subject_service.list_subjects(limit=3)
        assert len(results) == 3

    def test_list_subjects_combined_filters(self, subject_service):
        subject_service.create_subject(subject_code="MAT01", title="Maths KS3", key_stage="KS3", department="Maths")
        subject_service.create_subject(subject_code="MAT02", title="Maths KS4", key_stage="KS4", department="Maths")
        subject_service.create_subject(subject_code="ENG01", title="English KS3", key_stage="KS3", department="English")
        results = subject_service.list_subjects(key_stage="KS3", department="Maths")
        assert len(results) == 1
        assert results[0]["subject_code"] == "MAT01"


class TestUpdateSubject:
    """Tests for updating subjects."""

    def test_update_title(self, subject_service, sample_subject):
        updated = subject_service.update_subject(
            sample_subject["id"], title="Advanced Mathematics",
        )
        assert updated["title"] == "Advanced Mathematics"
        assert updated["subject_code"] == "MAT01"  # unchanged

    def test_update_capacity(self, subject_service, sample_subject):
        updated = subject_service.update_subject(
            sample_subject["id"], capacity=25,
        )
        assert updated["capacity"] == 25

    def test_update_multiple_fields(self, subject_service, sample_subject):
        updated = subject_service.update_subject(
            sample_subject["id"],
            title="Further Maths", capacity=20, teacher="Dr Smith", room="M202",
        )
        assert updated["title"] == "Further Maths"
        assert updated["capacity"] == 20
        assert updated["teacher"] == "Dr Smith"
        assert updated["room"] == "M202"

    def test_update_no_fields_raises(self, subject_service, sample_subject):
        with pytest.raises(ValidationError, match="No valid fields"):
            subject_service.update_subject(sample_subject["id"])

    def test_update_unknown_fields_raises(self, subject_service, sample_subject):
        with pytest.raises(ValidationError, match="No valid fields"):
            subject_service.update_subject(sample_subject["id"], unknown_field="value")

    def test_update_sets_updated_at(self, subject_service, sample_subject):
        updated = subject_service.update_subject(sample_subject["id"], title="Updated")
        assert updated["updated_at"] is not None

    def test_update_status(self, subject_service, sample_subject):
        updated = subject_service.update_subject(sample_subject["id"], status="inactive")
        assert updated["status"] == "inactive"

    def test_update_key_stage(self, subject_service, sample_subject):
        updated = subject_service.update_subject(sample_subject["id"], key_stage="KS4")
        assert updated["key_stage"] == "KS4"


class TestDeleteSubject:
    """Tests for deleting subjects."""

    def test_delete_subject(self, subject_service, sample_subject):
        result = subject_service.delete_subject(sample_subject["id"])
        assert result is True
        assert subject_service.get_subject(sample_subject["id"]) is None

    def test_delete_subject_with_enrollments(self, subject_service, enrollment_service,
                                              student_service, sample_subject):
        """Deleting a subject should remove related enrollments."""
        student = student_service.create_student(first_name="A", last_name="One")
        enrollment_service.enroll_student(student["id"], sample_subject["id"])
        subject_service.delete_subject(sample_subject["id"])
        assert subject_service.get_subject(sample_subject["id"]) is None
        enrollments = enrollment_service.get_student_enrollments(student["id"])
        assert len(enrollments) == 0

    def test_delete_nonexistent_subject_no_error(self, subject_service):
        # delete_subject does not check existence first; it just runs DELETE
        result = subject_service.delete_subject(9999)
        assert result is True

    def test_is_core_flag_persisted(self, subject_service, sample_subject):
        assert sample_subject["is_core"] == 1
        updated = subject_service.update_subject(sample_subject["id"], is_core=0)
        assert updated["is_core"] == 0
