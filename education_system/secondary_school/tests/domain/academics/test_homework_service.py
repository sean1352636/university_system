"""Tests for HomeworkService."""

import pytest
from education_system.secondary_school.core.exceptions import HomeworkError


class TestCreateHomework:
    """Tests for creating homework."""

    def test_create_homework_returns_dict(self, homework_service, sample_subject):
        hw = homework_service.create_homework(
            subject_id=sample_subject["id"],
            title="Fractions Worksheet",
            due_date="2025-12-10",
            year_group="9",
            description="Pages 30-35",
            max_marks=20,
        )
        assert isinstance(hw, dict)
        assert hw["title"] == "Fractions Worksheet"
        assert hw["subject_id"] == sample_subject["id"]
        assert hw["due_date"] == "2025-12-10"
        assert hw["max_marks"] == 20


class TestListHomework:
    """Tests for listing homework."""

    def test_list_homework_returns_created(self, homework_service, sample_subject):
        homework_service.create_homework(
            subject_id=sample_subject["id"], title="HW 1", due_date="2025-12-01",
        )
        homework_service.create_homework(
            subject_id=sample_subject["id"], title="HW 2", due_date="2025-12-05",
        )
        items = homework_service.list_homework()
        assert len(items) >= 2
        titles = [h["title"] for h in items]
        assert "HW 1" in titles
        assert "HW 2" in titles

    def test_list_homework_filters_by_subject(
        self, homework_service, sample_subject, sample_subject_science
    ):
        homework_service.create_homework(
            subject_id=sample_subject["id"], title="Maths HW", due_date="2025-12-01",
        )
        homework_service.create_homework(
            subject_id=sample_subject_science["id"], title="Science HW",
            due_date="2025-12-01",
        )
        maths_hw = homework_service.list_homework(subject_id=sample_subject["id"])
        assert all(h["subject_id"] == sample_subject["id"] for h in maths_hw)
        assert any(h["title"] == "Maths HW" for h in maths_hw)


class TestDeleteHomework:
    """Tests for deleting homework."""

    def test_delete_homework_removes_hw_and_submissions(
        self, homework_service, sample_homework, sample_student
    ):
        homework_service.submit(sample_homework["id"], sample_student["id"])
        homework_service.delete_homework(sample_homework["id"])
        items = homework_service.list_homework()
        assert all(h["id"] != sample_homework["id"] for h in items)
        subs = homework_service.get_submissions(sample_homework["id"])
        assert len(subs) == 0


class TestSubmit:
    """Tests for homework submission."""

    def test_submit_creates_submission(
        self, homework_service, sample_homework, sample_student
    ):
        homework_service.submit(sample_homework["id"], sample_student["id"])
        subs = homework_service.get_submissions(sample_homework["id"])
        assert len(subs) == 1
        assert subs[0]["status"] == "submitted"

    def test_submit_updates_existing(
        self, homework_service, sample_homework, sample_student
    ):
        homework_service.submit(sample_homework["id"], sample_student["id"])
        homework_service.submit(sample_homework["id"], sample_student["id"])
        subs = homework_service.get_submissions(sample_homework["id"])
        assert len(subs) == 1


class TestMarkSubmission:
    """Tests for marking submissions."""

    def test_mark_submission(
        self, homework_service, sample_homework, sample_student
    ):
        homework_service.submit(sample_homework["id"], sample_student["id"])
        homework_service.mark_submission(
            sample_homework["id"], sample_student["id"],
            marks=42, feedback="Good work",
        )
        subs = homework_service.get_submissions(sample_homework["id"])
        assert subs[0]["status"] == "marked"
        assert subs[0]["marks"] == 42
        assert subs[0]["feedback"] == "Good work"


class TestGetSubmissions:
    """Tests for getting submissions."""

    def test_get_submissions_returns_student_info(
        self, homework_service, sample_homework, student_service
    ):
        s1 = student_service.create_student(first_name="Tom", last_name="Jones")
        homework_service.submit(sample_homework["id"], s1["id"])
        subs = homework_service.get_submissions(sample_homework["id"])
        assert len(subs) == 1
        assert subs[0]["first_name"] == "Tom"
        assert subs[0]["last_name"] == "Jones"


class TestRubric:
    """Tests for homework rubrics."""

    def test_add_rubric_creates_criterion(
        self, homework_service, sample_homework
    ):
        rubric = homework_service.add_rubric(
            sample_homework["id"], "Clear working shown", 10,
        )
        assert isinstance(rubric, dict)
        assert rubric["criteria"] == "Clear working shown"
        assert rubric["max_marks"] == 10
        assert rubric["homework_id"] == sample_homework["id"]

    def test_add_rubric_empty_criteria_raises(
        self, homework_service, sample_homework
    ):
        with pytest.raises(HomeworkError, match="Criteria text is required"):
            homework_service.add_rubric(sample_homework["id"], "", 10)

    def test_get_rubric_returns_list(
        self, homework_service, sample_homework
    ):
        homework_service.add_rubric(sample_homework["id"], "Accuracy", 5)
        homework_service.add_rubric(sample_homework["id"], "Method", 5)
        rubric = homework_service.get_rubric(sample_homework["id"])
        assert len(rubric) == 2
        criteria_texts = [r["criteria"] for r in rubric]
        assert "Accuracy" in criteria_texts
        assert "Method" in criteria_texts


class TestDrafts:
    """Tests for homework drafts."""

    def test_save_draft_creates(
        self, homework_service, sample_homework, sample_student
    ):
        homework_service.save_draft(
            sample_homework["id"], sample_student["id"], "My draft answer",
        )
        draft = homework_service.get_draft(
            sample_homework["id"], sample_student["id"],
        )
        assert draft is not None
        assert draft["draft_text"] == "My draft answer"

    def test_save_draft_upserts(
        self, homework_service, sample_homework, sample_student
    ):
        homework_service.save_draft(
            sample_homework["id"], sample_student["id"], "First draft",
        )
        homework_service.save_draft(
            sample_homework["id"], sample_student["id"], "Updated draft",
        )
        draft = homework_service.get_draft(
            sample_homework["id"], sample_student["id"],
        )
        assert draft["draft_text"] == "Updated draft"

    def test_get_draft_returns_none_when_missing(
        self, homework_service, sample_homework, sample_student
    ):
        draft = homework_service.get_draft(
            sample_homework["id"], sample_student["id"],
        )
        assert draft is None


class TestSubmissionStats:
    """Tests for submission statistics."""

    def test_get_submission_stats_returns_counts(
        self, homework_service, sample_homework, student_service
    ):
        s1 = student_service.create_student(first_name="A", last_name="One")
        s2 = student_service.create_student(first_name="B", last_name="Two")
        homework_service.submit(sample_homework["id"], s1["id"])
        homework_service.submit(sample_homework["id"], s2["id"])
        homework_service.mark_submission(
            sample_homework["id"], s1["id"], marks=40,
        )
        stats = homework_service.get_submission_stats(sample_homework["id"])
        assert stats["total_submissions"] == 2
        assert stats["marked_count"] == 1


class TestExtendDeadline:
    """Tests for extending homework deadlines."""

    def test_extend_deadline_updates_due_date(
        self, homework_service, sample_homework
    ):
        result = homework_service.extend_deadline(
            sample_homework["id"], "2025-12-31", "Snow day",
        )
        assert result["due_date"] == "2025-12-31"

    def test_extend_deadline_earlier_date_raises(
        self, homework_service, sample_homework
    ):
        with pytest.raises(HomeworkError, match="later than the current"):
            homework_service.extend_deadline(
                sample_homework["id"], "2025-12-01", "No reason",
            )
