"""Tests for ProgressService."""

import pytest
from education_system.secondary_school.core.exceptions import ProgressError


class TestSetTarget:
    """Tests for setting progress targets."""

    def test_set_target_creates_new(
        self, progress_service, sample_student, sample_subject
    ):
        progress_service.set_target(
            sample_student["id"], sample_subject["id"],
            academic_year="2025/2026",
            baseline_grade="5", target_grade="7",
        )
        targets = progress_service.list_student_progress(sample_student["id"])
        assert len(targets) == 1
        assert targets[0]["baseline_grade"] == "5"
        assert targets[0]["target_grade"] == "7"

    def test_set_target_upserts_existing(
        self, progress_service, sample_student, sample_subject
    ):
        progress_service.set_target(
            sample_student["id"], sample_subject["id"],
            academic_year="2025/2026",
            baseline_grade="4", target_grade="6",
        )
        progress_service.set_target(
            sample_student["id"], sample_subject["id"],
            academic_year="2025/2026",
            baseline_grade="5", target_grade="7",
        )
        targets = progress_service.list_student_progress(
            sample_student["id"], academic_year="2025/2026",
        )
        assert len(targets) == 1
        assert targets[0]["target_grade"] == "7"


class TestUpdateGrade:
    """Tests for updating term grades."""

    def test_update_grade_sets_term_and_current(
        self, progress_service, sample_student, sample_subject
    ):
        progress_service.set_target(
            sample_student["id"], sample_subject["id"],
            baseline_grade="5", target_grade="7",
        )
        targets = progress_service.list_student_progress(sample_student["id"])
        target_id = targets[0]["id"]
        progress_service.update_grade(target_id, "autumn", "6")
        updated = progress_service.list_student_progress(sample_student["id"])
        assert updated[0]["autumn_grade"] == "6"
        assert updated[0]["current_grade"] == "6"


class TestListStudentProgress:
    """Tests for listing student progress."""

    def test_list_student_progress_returns_subject_info(
        self, progress_service, sample_student, sample_subject
    ):
        progress_service.set_target(
            sample_student["id"], sample_subject["id"],
            baseline_grade="5", target_grade="7",
        )
        targets = progress_service.list_student_progress(sample_student["id"])
        assert len(targets) == 1
        assert targets[0]["subject_name"] == "Mathematics"
        assert targets[0]["subject_code"] == "MAT01"


class TestListSubjectProgress:
    """Tests for listing subject progress."""

    def test_list_subject_progress_returns_student_info(
        self, progress_service, student_service, sample_subject
    ):
        s1 = student_service.create_student(
            first_name="Tom", last_name="Alpha", year_group="9",
        )
        progress_service.set_target(
            s1["id"], sample_subject["id"],
            baseline_grade="4", target_grade="6",
        )
        targets = progress_service.list_subject_progress(sample_subject["id"])
        assert len(targets) == 1
        assert targets[0]["first_name"] == "Tom"
        assert targets[0]["last_name"] == "Alpha"


class TestListAll:
    """Tests for listing all progress targets."""

    def test_list_all_returns_targets(
        self, progress_service, sample_student, sample_subject
    ):
        progress_service.set_target(
            sample_student["id"], sample_subject["id"],
            academic_year="2025/2026",
            baseline_grade="5", target_grade="7",
        )
        all_targets = progress_service.list_all(academic_year="2025/2026")
        assert len(all_targets) >= 1

    def test_list_all_filters_by_year_group(
        self, progress_service, student_service, sample_subject
    ):
        s9 = student_service.create_student(
            first_name="Y9", last_name="Student", year_group="9",
        )
        s10 = student_service.create_student(
            first_name="Y10", last_name="Student", year_group="10",
        )
        progress_service.set_target(
            s9["id"], sample_subject["id"], academic_year="2025/2026",
            baseline_grade="5", target_grade="7",
        )
        progress_service.set_target(
            s10["id"], sample_subject["id"], academic_year="2025/2026",
            baseline_grade="4", target_grade="6",
        )
        y9_targets = progress_service.list_all(
            year_group="9", academic_year="2025/2026",
        )
        assert all(t["year_group"] == "9" for t in y9_targets)
        assert len(y9_targets) >= 1


class TestDeleteTarget:
    """Tests for deleting progress targets."""

    def test_delete_target_removes(
        self, progress_service, sample_student, sample_subject
    ):
        progress_service.set_target(
            sample_student["id"], sample_subject["id"],
            baseline_grade="5", target_grade="7",
        )
        targets = progress_service.list_student_progress(sample_student["id"])
        target_id = targets[0]["id"]
        progress_service.delete_target(target_id)
        remaining = progress_service.list_student_progress(sample_student["id"])
        assert len(remaining) == 0
