"""Comprehensive tests for GradeService."""

import pytest
from education_system.secondary_school.core.exceptions import GradeError


class TestAddGrade:
    """Tests for adding grades."""

    def test_add_grade_basic(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"],
            subject_id=sample_subject["id"],
            score=85.0,
            grade="8",
        )
        assert grade["score"] == 85.0
        assert grade["grade"] == "8"
        assert grade["student_id"] == enrolled_student["id"]
        assert grade["subject_id"] == sample_subject["id"]

    def test_add_grade_with_all_fields(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"],
            subject_id=sample_subject["id"],
            assessment_type="test",
            assessment_name="Autumn Test 1",
            score=85.0,
            grade="8",
            term="Autumn",
            academic_year="2025-2026",
            teacher_comment="Excellent work",
        )
        assert grade["assessment_type"] == "test"
        assert grade["assessment_name"] == "Autumn Test 1"
        assert grade["term"] == "Autumn"
        assert grade["academic_year"] == "2025-2026"
        assert grade["teacher_comment"] == "Excellent work"

    def test_add_grade_default_assessment_type(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"],
            subject_id=sample_subject["id"],
            score=70.0,
        )
        assert grade["assessment_type"] == "classwork"

    def test_add_grade_various_types(self, grade_service, enrolled_student, sample_subject):
        for atype in ("homework", "test", "mock_exam", "coursework", "end_of_term"):
            grade = grade_service.add_grade(
                student_id=enrolled_student["id"],
                subject_id=sample_subject["id"],
                assessment_type=atype,
                score=75.0,
            )
            assert grade["assessment_type"] == atype

    def test_add_grade_score_only(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"],
            subject_id=sample_subject["id"],
            score=90.0,
        )
        assert grade["score"] == 90.0
        assert grade["grade"] is None

    def test_add_grade_grade_only(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"],
            subject_id=sample_subject["id"],
            grade="9",
        )
        assert grade["grade"] == "9"
        assert grade["score"] is None

    def test_add_multiple_grades_same_student(self, grade_service, enrolled_student, sample_subject):
        g1 = grade_service.add_grade(
            student_id=enrolled_student["id"],
            subject_id=sample_subject["id"],
            score=70.0, grade="6",
        )
        g2 = grade_service.add_grade(
            student_id=enrolled_student["id"],
            subject_id=sample_subject["id"],
            score=85.0, grade="8",
        )
        assert g1["id"] != g2["id"]

    def test_add_grade_zero_score(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"],
            subject_id=sample_subject["id"],
            score=0.0, grade="1",
        )
        assert grade["score"] == 0.0

    def test_add_grade_full_score(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"],
            subject_id=sample_subject["id"],
            score=100.0, grade="9",
        )
        assert grade["score"] == 100.0


class TestGetStudentGrades:
    """Tests for retrieving student grades."""

    def test_get_student_grades_empty(self, grade_service, enrolled_student):
        grades = grade_service.get_student_grades(enrolled_student["id"])
        assert len(grades) == 0

    def test_get_student_grades_all(self, grade_service, enrolled_student, sample_subject):
        grade_service.add_grade(student_id=enrolled_student["id"], subject_id=sample_subject["id"], score=75.0, grade="7")
        grade_service.add_grade(student_id=enrolled_student["id"], subject_id=sample_subject["id"], score=80.0, grade="7")
        grades = grade_service.get_student_grades(enrolled_student["id"])
        assert len(grades) == 2

    def test_get_student_grades_by_subject(self, grade_service, enrolled_student_multi,
                                            sample_subject, sample_subject_science):
        grade_service.add_grade(
            student_id=enrolled_student_multi["id"],
            subject_id=sample_subject["id"], score=70.0,
        )
        grade_service.add_grade(
            student_id=enrolled_student_multi["id"],
            subject_id=sample_subject_science["id"], score=80.0,
        )
        maths_grades = grade_service.get_student_grades(
            enrolled_student_multi["id"], subject_id=sample_subject["id"],
        )
        assert len(maths_grades) == 1
        assert maths_grades[0]["score"] == 70.0

    def test_get_student_grades_by_term(self, grade_service, enrolled_student, sample_subject):
        grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=70.0, term="Autumn",
        )
        grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=80.0, term="Spring",
        )
        autumn = grade_service.get_student_grades(enrolled_student["id"], term="Autumn")
        assert len(autumn) == 1
        assert autumn[0]["term"] == "Autumn"

    def test_get_student_grades_includes_subject_info(self, grade_service, enrolled_student, sample_subject):
        grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"], score=75.0,
        )
        grades = grade_service.get_student_grades(enrolled_student["id"])
        assert grades[0]["subject_code"] == "MAT01"
        assert grades[0]["title"] == "Mathematics"


class TestGetSubjectGrades:
    """Tests for retrieving subject-wide grades."""

    def test_get_subject_grades(self, grade_service, student_service, sample_subject, enrollment_service):
        s1 = student_service.create_student(first_name="A", last_name="One")
        s2 = student_service.create_student(first_name="B", last_name="Two")
        enrollment_service.enroll_student(s1["id"], sample_subject["id"])
        enrollment_service.enroll_student(s2["id"], sample_subject["id"])
        grade_service.add_grade(student_id=s1["id"], subject_id=sample_subject["id"], score=90.0)
        grade_service.add_grade(student_id=s2["id"], subject_id=sample_subject["id"], score=60.0)
        grades = grade_service.get_subject_grades(sample_subject["id"])
        assert len(grades) == 2

    def test_get_subject_grades_empty(self, grade_service, sample_subject):
        grades = grade_service.get_subject_grades(sample_subject["id"])
        assert len(grades) == 0

    def test_get_subject_grades_includes_student_info(self, grade_service, student_service,
                                                       sample_subject, enrollment_service):
        s1 = student_service.create_student(first_name="Alice", last_name="Wonder")
        enrollment_service.enroll_student(s1["id"], sample_subject["id"])
        grade_service.add_grade(student_id=s1["id"], subject_id=sample_subject["id"], score=85.0)
        grades = grade_service.get_subject_grades(sample_subject["id"])
        assert grades[0]["first_name"] == "Alice"
        assert grades[0]["last_name"] == "Wonder"

    def test_get_subject_grades_by_assessment_name(self, grade_service, student_service,
                                                    sample_subject, enrollment_service):
        s1 = student_service.create_student(first_name="A", last_name="One")
        enrollment_service.enroll_student(s1["id"], sample_subject["id"])
        grade_service.add_grade(
            student_id=s1["id"], subject_id=sample_subject["id"],
            score=85.0, assessment_name="Test 1",
        )
        grade_service.add_grade(
            student_id=s1["id"], subject_id=sample_subject["id"],
            score=90.0, assessment_name="Test 2",
        )
        test1 = grade_service.get_subject_grades(sample_subject["id"], assessment_name="Test 1")
        assert len(test1) == 1
        assert test1[0]["score"] == 85.0


class TestUpdateGrade:
    """Tests for updating grades."""

    def test_update_score(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=50.0, grade="5",
        )
        updated = grade_service.update_grade(grade["id"], score=65.0)
        assert updated["score"] == 65.0
        assert updated["grade"] == "5"  # unchanged

    def test_update_grade_letter(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=50.0, grade="5",
        )
        updated = grade_service.update_grade(grade["id"], grade="6")
        assert updated["grade"] == "6"

    def test_update_multiple_fields(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=50.0, grade="5",
        )
        updated = grade_service.update_grade(
            grade["id"], score=75.0, grade="7",
            teacher_comment="Much improved",
        )
        assert updated["score"] == 75.0
        assert updated["grade"] == "7"
        assert updated["teacher_comment"] == "Much improved"

    def test_update_no_fields_raises(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=50.0,
        )
        with pytest.raises(GradeError, match="No valid fields"):
            grade_service.update_grade(grade["id"])

    def test_update_assessment_type(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=50.0, assessment_type="classwork",
        )
        updated = grade_service.update_grade(grade["id"], assessment_type="test")
        assert updated["assessment_type"] == "test"

    def test_update_term(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=50.0, term="Autumn",
        )
        updated = grade_service.update_grade(grade["id"], term="Spring")
        assert updated["term"] == "Spring"


class TestDeleteGrade:
    """Tests for deleting grades."""

    def test_delete_grade(self, grade_service, enrolled_student, sample_subject):
        grade = grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=50.0,
        )
        result = grade_service.delete_grade(grade["id"])
        assert result is True

    def test_delete_grade_removes_from_list(self, grade_service, enrolled_student, sample_subject):
        g1 = grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=50.0,
        )
        g2 = grade_service.add_grade(
            student_id=enrolled_student["id"], subject_id=sample_subject["id"],
            score=80.0,
        )
        grade_service.delete_grade(g1["id"])
        remaining = grade_service.get_student_grades(enrolled_student["id"])
        assert len(remaining) == 1
        assert remaining[0]["score"] == 80.0

    def test_delete_nonexistent_grade(self, grade_service):
        # delete_grade does not raise for non-existent; it just runs DELETE
        result = grade_service.delete_grade(9999)
        assert result is True


class TestStudentAverage:
    """Tests for calculating student averages."""

    def test_student_average(self, grade_service, enrolled_student, sample_subject):
        grade_service.add_grade(student_id=enrolled_student["id"], subject_id=sample_subject["id"], score=80.0)
        grade_service.add_grade(student_id=enrolled_student["id"], subject_id=sample_subject["id"], score=60.0)
        avg = grade_service.get_student_average(enrolled_student["id"])
        assert avg == 70.0

    def test_student_average_single_grade(self, grade_service, enrolled_student, sample_subject):
        grade_service.add_grade(student_id=enrolled_student["id"], subject_id=sample_subject["id"], score=85.0)
        avg = grade_service.get_student_average(enrolled_student["id"])
        assert avg == 85.0

    def test_student_average_no_grades(self, grade_service, enrolled_student):
        avg = grade_service.get_student_average(enrolled_student["id"])
        assert avg is None

    def test_student_average_per_subject(self, grade_service, enrolled_student_multi,
                                         sample_subject, sample_subject_science):
        grade_service.add_grade(student_id=enrolled_student_multi["id"], subject_id=sample_subject["id"], score=90.0)
        grade_service.add_grade(student_id=enrolled_student_multi["id"], subject_id=sample_subject["id"], score=80.0)
        grade_service.add_grade(student_id=enrolled_student_multi["id"], subject_id=sample_subject_science["id"], score=60.0)
        maths_avg = grade_service.get_student_average(enrolled_student_multi["id"], subject_id=sample_subject["id"])
        assert maths_avg == 85.0
        science_avg = grade_service.get_student_average(enrolled_student_multi["id"], subject_id=sample_subject_science["id"])
        assert science_avg == 60.0
        overall_avg = grade_service.get_student_average(enrolled_student_multi["id"])
        # (90 + 80 + 60) / 3 = 76.67
        assert round(overall_avg, 2) == 76.67

    def test_student_average_ignores_null_scores(self, grade_service, enrolled_student, sample_subject):
        grade_service.add_grade(student_id=enrolled_student["id"], subject_id=sample_subject["id"], score=80.0)
        grade_service.add_grade(student_id=enrolled_student["id"], subject_id=sample_subject["id"], grade="7")  # no score
        avg = grade_service.get_student_average(enrolled_student["id"])
        assert avg == 80.0

    def test_student_average_with_zero_score(self, grade_service, enrolled_student, sample_subject):
        grade_service.add_grade(student_id=enrolled_student["id"], subject_id=sample_subject["id"], score=0.0)
        grade_service.add_grade(student_id=enrolled_student["id"], subject_id=sample_subject["id"], score=100.0)
        avg = grade_service.get_student_average(enrolled_student["id"])
        assert avg == 50.0
