"""Tests for PastoralService."""

import pytest


class TestPastoralService:
    @pytest.fixture
    def pastoral_service(self, db_path):
        from education_system.college_system.modules.domain.pastoral.services.pastoral_service import PastoralService
        return PastoralService(db_path)

    def test_add_note(self, pastoral_service, sample_student):
        note = pastoral_service.add_note(
            student_id=sample_student["id"],
            author_id=1,
            category="academic",
            content="Student struggling with workload",
        )
        assert note["category"] == "academic"
        assert note["content"] == "Student struggling with workload"

    def test_list_notes(self, pastoral_service, sample_student):
        pastoral_service.add_note(
            student_id=sample_student["id"], author_id=1,
            category="welfare", content="Note 1",
        )
        pastoral_service.add_note(
            student_id=sample_student["id"], author_id=1,
            category="academic", content="Note 2",
        )
        notes = pastoral_service.list_notes(student_id=sample_student["id"])
        assert len(notes) >= 2

    def test_list_notes_filter_category(self, pastoral_service, sample_student):
        pastoral_service.add_note(
            student_id=sample_student["id"], author_id=1,
            category="welfare", content="Welfare note",
        )
        pastoral_service.add_note(
            student_id=sample_student["id"], author_id=1,
            category="academic", content="Academic note",
        )
        welfare = pastoral_service.list_notes(category="welfare")
        assert all(n["category"] == "welfare" for n in welfare)

    def test_get_note(self, pastoral_service, sample_student):
        created = pastoral_service.add_note(
            student_id=sample_student["id"], author_id=1,
            category="welfare", content="Confidential note",
        )
        found = pastoral_service.get_note(created["id"])
        assert found["content"] == "Confidential note"

    def test_record_wellbeing(self, pastoral_service, sample_student):
        record = pastoral_service.record_wellbeing(
            student_id=sample_student["id"],
            recorded_by=1,
            wellbeing_score=3,
            concerns="Seems tired",
        )
        assert record["wellbeing_score"] == 3
