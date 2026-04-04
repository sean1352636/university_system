"""Tests for PastoralService."""
import pytest
from education_system.secondary_school.core.exceptions import PastoralError


class TestAddNote:
    def test_add_note_creates_pastoral_note(self, pastoral_service, sample_student):
        n = pastoral_service.add_note(
            student_id=sample_student["id"],
            content="Student seemed upset today",
            note_type="welfare", recorded_by="Mrs Brown",
        )
        assert n["student_id"] == sample_student["id"]
        assert n["content"] == "Student seemed upset today"
        assert n["note_type"] == "welfare"
        assert n["recorded_by"] == "Mrs Brown"

    def test_add_note_with_confidential_flag(self, pastoral_service, sample_student):
        n = pastoral_service.add_note(
            student_id=sample_student["id"],
            content="Sensitive family information",
            note_type="family", is_confidential=True,
        )
        assert n["is_confidential"] == 1


class TestListNotes:
    def test_list_returns_notes(self, pastoral_service, sample_student):
        pastoral_service.add_note(sample_student["id"], "Note 1")
        pastoral_service.add_note(sample_student["id"], "Note 2")
        result = pastoral_service.list_notes()
        assert len(result) >= 2

    def test_list_filter_by_student(self, pastoral_service, sample_student, sample_student_ks4):
        pastoral_service.add_note(sample_student["id"], "Note A")
        pastoral_service.add_note(sample_student_ks4["id"], "Note B")
        result = pastoral_service.list_notes(student_id=sample_student["id"])
        assert len(result) == 1
        assert result[0]["student_id"] == sample_student["id"]

    def test_list_filter_by_note_type(self, pastoral_service, sample_student):
        pastoral_service.add_note(sample_student["id"], "N1", note_type="welfare")
        pastoral_service.add_note(sample_student["id"], "N2", note_type="academic")
        result = pastoral_service.list_notes(note_type="welfare")
        assert len(result) == 1
        assert result[0]["note_type"] == "welfare"


class TestNoteActions:
    def test_mark_follow_up_done(self, pastoral_service, sample_student):
        n = pastoral_service.add_note(
            sample_student["id"], "Needs follow-up",
            follow_up_date="2026-04-01",
        )
        pastoral_service.mark_follow_up_done(n["id"])
        notes = pastoral_service.list_notes(student_id=sample_student["id"])
        updated = [x for x in notes if x["id"] == n["id"]][0]
        assert updated["follow_up_done"] == 1

    def test_delete_note(self, pastoral_service, sample_student):
        n = pastoral_service.add_note(sample_student["id"], "Temp note")
        pastoral_service.delete_note(n["id"])
        result = pastoral_service.list_notes()
        assert all(x["id"] != n["id"] for x in result)


class TestHousePoints:
    def test_award_house_points(self, pastoral_service, sample_student):
        pastoral_service.award_house_points(
            student_id=sample_student["id"], house="Gryffindor",
            points=5, reason="Helping others", awarded_by="Mr Smith",
        )
        pts = pastoral_service.student_house_points(sample_student["id"])
        assert len(pts) == 1
        assert pts[0]["house"] == "Gryffindor"
        assert pts[0]["points"] == 5

    def test_house_points_summary(self, pastoral_service, sample_student, sample_student_ks4):
        pastoral_service.award_house_points(sample_student["id"], "Red", points=10)
        pastoral_service.award_house_points(sample_student_ks4["id"], "Blue", points=7)
        pastoral_service.award_house_points(sample_student["id"], "Red", points=5)
        summary = pastoral_service.house_points_summary()
        assert len(summary) == 2
        red = [s for s in summary if s["house"] == "Red"][0]
        blue = [s for s in summary if s["house"] == "Blue"][0]
        assert red["total"] == 15
        assert blue["total"] == 7

    def test_student_house_points_returns_individual(self, pastoral_service, sample_student):
        pastoral_service.award_house_points(sample_student["id"], "Green", points=3)
        pastoral_service.award_house_points(sample_student["id"], "Green", points=2)
        pts = pastoral_service.student_house_points(sample_student["id"])
        assert len(pts) == 2
        total = sum(p["points"] for p in pts)
        assert total == 5
