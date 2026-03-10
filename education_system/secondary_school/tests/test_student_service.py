"""Comprehensive tests for StudentService."""

import pytest
from education_system.secondary_school.core.exceptions import StudentError, ValidationError


class TestCreateStudent:
    """Tests for creating students."""

    def test_create_student_basic(self, student_service):
        student = student_service.create_student(
            first_name="Alice", last_name="Smith",
            email="alice@school.local", year_group="7",
        )
        assert student["first_name"] == "Alice"
        assert student["last_name"] == "Smith"
        assert student["email"] == "alice@school.local"
        assert student["student_id"].startswith("SEC")
        assert student["year_group"] == "7"
        assert student["key_stage"] == "KS3"
        assert student["status"] == "active"

    def test_create_student_ks3_year_groups(self, student_service):
        for year in ["7", "8", "9"]:
            student = student_service.create_student(
                first_name=f"Student{year}", last_name="Test", year_group=year,
            )
            assert student["key_stage"] == "KS3"

    def test_create_student_ks4_year_groups(self, student_service):
        for year in ["10", "11"]:
            student = student_service.create_student(
                first_name=f"Student{year}", last_name="Test", year_group=year,
            )
            assert student["key_stage"] == "KS4"

    def test_create_student_defaults_year_7(self, student_service):
        student = student_service.create_student(
            first_name="NoYear", last_name="Student",
        )
        assert student["year_group"] == "7"
        assert student["key_stage"] == "KS3"

    def test_create_student_with_all_fields(self, student_service):
        student = student_service.create_student(
            first_name="Complete", last_name="Record",
            email="complete@school.local",
            date_of_birth="2012-03-15",
            address="123 School Lane",
            year_group="8", form_group="8C",
            form_tutor="Mr Adams",
            sen_status="ehcp",
            pupil_premium=True,
            parent_name="Mrs Record",
            parent_email="parent@example.com",
            parent_phone="07700900001",
            emergency_contact_name="Gran Record",
            emergency_contact_phone="07700900002",
        )
        assert student["date_of_birth"] == "2012-03-15"
        assert student["address"] == "123 School Lane"
        assert student["form_group"] == "8C"
        assert student["form_tutor"] == "Mr Adams"
        assert student["sen_status"] == "ehcp"
        assert student["pupil_premium"] == 1
        assert student["parent_name"] == "Mrs Record"
        assert student["parent_email"] == "parent@example.com"
        assert student["emergency_contact_name"] == "Gran Record"

    def test_create_student_validates_empty_first_name(self, student_service):
        with pytest.raises(ValidationError):
            student_service.create_student(first_name="", last_name="Smith")

    def test_create_student_validates_empty_last_name(self, student_service):
        with pytest.raises(ValidationError):
            student_service.create_student(first_name="Alice", last_name="")

    def test_create_student_validates_email_format(self, student_service):
        with pytest.raises(ValidationError):
            student_service.create_student(
                first_name="Alice", last_name="Smith", email="not-an-email",
            )

    def test_create_student_validates_parent_email(self, student_service):
        with pytest.raises(ValidationError):
            student_service.create_student(
                first_name="Alice", last_name="Smith",
                parent_email="bad-email",
            )

    def test_create_student_no_email_is_valid(self, student_service):
        student = student_service.create_student(
            first_name="NoEmail", last_name="Student",
        )
        assert student["email"] is None

    def test_create_student_sen_status_defaults_none(self, student_service):
        student = student_service.create_student(
            first_name="Default", last_name="SEN",
        )
        assert student["sen_status"] == "none"

    def test_pupil_premium_flag(self, student_service):
        student = student_service.create_student(
            first_name="PP", last_name="Student", pupil_premium=True,
        )
        assert student["pupil_premium"] == 1

    def test_pupil_premium_default_false(self, student_service):
        student = student_service.create_student(
            first_name="NoPP", last_name="Student",
        )
        assert student["pupil_premium"] == 0

    def test_sequential_student_ids(self, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One")
        s2 = student_service.create_student(first_name="B", last_name="Two")
        s3 = student_service.create_student(first_name="C", last_name="Three")
        num1 = int(s1["student_id"].replace("SEC", ""))
        num2 = int(s2["student_id"].replace("SEC", ""))
        num3 = int(s3["student_id"].replace("SEC", ""))
        assert num2 == num1 + 1
        assert num3 == num2 + 1

    def test_student_id_format(self, student_service):
        student = student_service.create_student(first_name="A", last_name="B")
        assert student["student_id"].startswith("SEC")
        numeric_part = student["student_id"].replace("SEC", "")
        assert len(numeric_part) == 4
        assert numeric_part.isdigit()


class TestGetStudent:
    """Tests for retrieving students."""

    def test_get_student_by_pk(self, student_service, sample_student):
        found = student_service.get_student(sample_student["id"])
        assert found is not None
        assert found["first_name"] == "John"
        assert found["last_name"] == "Doe"

    def test_get_student_by_student_id(self, student_service, sample_student):
        found = student_service.get_student_by_student_id(sample_student["student_id"])
        assert found is not None
        assert found["last_name"] == "Doe"
        assert found["id"] == sample_student["id"]

    def test_get_nonexistent_student_returns_none(self, student_service):
        assert student_service.get_student(9999) is None

    def test_get_nonexistent_student_id_returns_none(self, student_service):
        assert student_service.get_student_by_student_id("SEC9999") is None

    def test_get_student_returns_all_fields(self, student_service, sample_student):
        found = student_service.get_student(sample_student["id"])
        assert "id" in found
        assert "student_id" in found
        assert "first_name" in found
        assert "last_name" in found
        assert "year_group" in found
        assert "key_stage" in found
        assert "status" in found


class TestListStudents:
    """Tests for listing and filtering students."""

    def test_list_students_empty(self, student_service):
        students = student_service.list_students()
        assert len(students) == 0

    def test_list_students_returns_all(self, student_service):
        student_service.create_student(first_name="A", last_name="One", year_group="7")
        student_service.create_student(first_name="B", last_name="Two", year_group="8")
        student_service.create_student(first_name="C", last_name="Three", year_group="9")
        students = student_service.list_students()
        assert len(students) == 3

    def test_list_students_filter_year_group(self, student_service):
        student_service.create_student(first_name="A", last_name="One", year_group="7")
        student_service.create_student(first_name="B", last_name="Two", year_group="8")
        student_service.create_student(first_name="C", last_name="Three", year_group="7")
        year7 = student_service.list_students(year_group="7")
        assert len(year7) == 2

    def test_list_students_filter_form_group(self, student_service):
        student_service.create_student(first_name="A", last_name="One", year_group="7", form_group="7A")
        student_service.create_student(first_name="B", last_name="Two", year_group="7", form_group="7B")
        group_a = student_service.list_students(form_group="7A")
        assert len(group_a) == 1
        assert group_a[0]["first_name"] == "A"

    def test_list_students_filter_key_stage(self, student_service):
        student_service.create_student(first_name="A", last_name="One", year_group="7")
        student_service.create_student(first_name="B", last_name="Two", year_group="10")
        ks3 = student_service.list_students(key_stage="KS3")
        assert len(ks3) == 1
        assert ks3[0]["key_stage"] == "KS3"

    def test_list_students_search_first_name(self, student_service):
        student_service.create_student(first_name="Alice", last_name="Wonder")
        student_service.create_student(first_name="Bob", last_name="Builder")
        results = student_service.list_students(search="Alice")
        assert len(results) == 1
        assert results[0]["first_name"] == "Alice"

    def test_list_students_search_last_name(self, student_service):
        student_service.create_student(first_name="Alice", last_name="Wonder")
        student_service.create_student(first_name="Bob", last_name="Builder")
        results = student_service.list_students(search="Builder")
        assert len(results) == 1
        assert results[0]["last_name"] == "Builder"

    def test_list_students_search_student_id(self, student_service):
        s1 = student_service.create_student(first_name="Alice", last_name="Wonder")
        student_service.create_student(first_name="Bob", last_name="Builder")
        results = student_service.list_students(search=s1["student_id"])
        assert len(results) == 1

    def test_list_students_search_case_insensitive(self, student_service):
        student_service.create_student(first_name="Alice", last_name="Wonder")
        results = student_service.list_students(search="alice")
        assert len(results) == 1

    def test_list_students_limit(self, student_service):
        for i in range(5):
            student_service.create_student(first_name=f"S{i}", last_name="Test")
        results = student_service.list_students(limit=3)
        assert len(results) == 3

    def test_list_students_offset(self, student_service):
        for i in range(5):
            student_service.create_student(first_name=f"S{i}", last_name="Test")
        all_students = student_service.list_students()
        offset_students = student_service.list_students(offset=2)
        assert len(offset_students) == 3
        assert offset_students[0]["id"] == all_students[2]["id"]

    def test_list_students_combined_filters(self, student_service):
        student_service.create_student(first_name="Alice", last_name="One", year_group="7", form_group="7A")
        student_service.create_student(first_name="Bob", last_name="Two", year_group="7", form_group="7B")
        student_service.create_student(first_name="Charlie", last_name="Three", year_group="8", form_group="8A")
        results = student_service.list_students(year_group="7", search="Alice")
        assert len(results) == 1


class TestUpdateStudent:
    """Tests for updating students."""

    def test_update_first_name(self, student_service, sample_student):
        updated = student_service.update_student(sample_student["id"], first_name="Jane")
        assert updated["first_name"] == "Jane"
        assert updated["last_name"] == "Doe"  # unchanged

    def test_update_year_group_updates_key_stage(self, student_service, sample_student):
        updated = student_service.update_student(sample_student["id"], year_group="11")
        assert updated["year_group"] == "11"
        assert updated["key_stage"] == "KS4"

    def test_update_multiple_fields(self, student_service, sample_student):
        updated = student_service.update_student(
            sample_student["id"],
            first_name="Jane", form_group="9B", sen_status="support_plan",
        )
        assert updated["first_name"] == "Jane"
        assert updated["form_group"] == "9B"
        assert updated["sen_status"] == "support_plan"

    def test_update_email_validates(self, student_service, sample_student):
        with pytest.raises(ValidationError):
            student_service.update_student(sample_student["id"], email="bad-email")

    def test_update_email_valid(self, student_service, sample_student):
        updated = student_service.update_student(
            sample_student["id"], email="new@school.local",
        )
        assert updated["email"] == "new@school.local"

    def test_update_no_fields_raises(self, student_service, sample_student):
        with pytest.raises(ValidationError, match="No valid fields"):
            student_service.update_student(sample_student["id"])

    def test_update_ignores_unknown_fields(self, student_service, sample_student):
        with pytest.raises(ValidationError, match="No valid fields"):
            student_service.update_student(sample_student["id"], unknown_field="value")

    def test_update_sets_updated_at(self, student_service, sample_student):
        updated = student_service.update_student(sample_student["id"], first_name="Jane")
        assert updated["updated_at"] is not None

    def test_update_status(self, student_service, sample_student):
        updated = student_service.update_student(sample_student["id"], status="inactive")
        assert updated["status"] == "inactive"


class TestDeleteStudent:
    """Tests for deleting students."""

    def test_delete_student(self, student_service, sample_student):
        result = student_service.delete_student(sample_student["id"])
        assert result is True
        assert student_service.get_student(sample_student["id"]) is None

    def test_delete_nonexistent_student_raises(self, student_service):
        with pytest.raises(StudentError, match="not found"):
            student_service.delete_student(9999)

    def test_delete_student_removes_related_data(self, student_service, grade_service,
                                                  enrollment_service, attendance_service,
                                                  sample_subject, db_path):
        """Deleting a student should cascade-delete grades, enrollments, attendance, behaviour."""
        student = student_service.create_student(
            first_name="Delete", last_name="Me", year_group="9",
        )
        enrollment_service.enroll_student(student["id"], sample_subject["id"])
        grade_service.add_grade(student_id=student["id"], subject_id=sample_subject["id"], score=75.0)
        attendance_service.record_attendance(student["id"], "2026-01-15", "present")

        student_service.delete_student(student["id"])

        # Verify cascading deletes
        assert student_service.get_student(student["id"]) is None
        enrollments = enrollment_service.get_student_enrollments(student["id"])
        assert len(enrollments) == 0
        grades = grade_service.get_student_grades(student["id"])
        assert len(grades) == 0
        attendance = attendance_service.get_student_attendance(student["id"])
        assert len(attendance) == 0


class TestCountStudents:
    """Tests for counting students."""

    def test_count_students_empty(self, student_service):
        assert student_service.count_students() == 0

    def test_count_students_all(self, student_service):
        student_service.create_student(first_name="A", last_name="One", year_group="7")
        student_service.create_student(first_name="B", last_name="Two", year_group="7")
        student_service.create_student(first_name="C", last_name="Three", year_group="8")
        assert student_service.count_students() == 3

    def test_count_students_by_year_group(self, student_service):
        student_service.create_student(first_name="A", last_name="One", year_group="7")
        student_service.create_student(first_name="B", last_name="Two", year_group="7")
        student_service.create_student(first_name="C", last_name="Three", year_group="8")
        assert student_service.count_students(year_group="7") == 2
        assert student_service.count_students(year_group="8") == 1
        assert student_service.count_students(year_group="9") == 0

    def test_count_active_students(self, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One")
        student_service.create_student(first_name="B", last_name="Two")
        student_service.update_student(s1["id"], status="inactive")
        assert student_service.count_students(status="active") == 1
        assert student_service.count_students(status="inactive") == 1
