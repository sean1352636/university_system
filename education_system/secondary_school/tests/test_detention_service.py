"""Tests for DetentionService."""
import pytest
from education_system.secondary_school.core.exceptions import DetentionError


class TestCreateDetention:
    def test_create_detention(self, detention_service, sample_student):
        d = detention_service.create_detention(
            student_id=sample_student["id"], reason="Disruption",
            date="2026-03-20", detention_type="lunchtime",
        )
        assert d["student_id"] == sample_student["id"]
        assert d["reason"] == "Disruption"
        assert d["detention_type"] == "lunchtime"
        assert d["status"] == "scheduled"

    def test_create_after_school_detention(self, detention_service, sample_student):
        d = detention_service.create_detention(
            student_id=sample_student["id"], reason="Late homework",
            date="2026-03-21", detention_type="after_school",
            start_time="15:15", end_time="16:00", room="D12", supervisor="Mr Jones",
        )
        assert d["detention_type"] == "after_school"
        assert d["room"] == "D12"


class TestListDetentions:
    def test_list_all(self, detention_service, sample_student):
        detention_service.create_detention(sample_student["id"], "R1", "2026-03-20")
        detention_service.create_detention(sample_student["id"], "R2", "2026-03-21")
        result = detention_service.list_detentions()
        assert len(result) >= 2

    def test_list_by_student(self, detention_service, sample_student, sample_student_ks4):
        detention_service.create_detention(sample_student["id"], "R1", "2026-03-20")
        detention_service.create_detention(sample_student_ks4["id"], "R2", "2026-03-21")
        result = detention_service.list_detentions(student_id=sample_student["id"])
        assert len(result) == 1


class TestDetentionActions:
    def test_mark_attended(self, detention_service, sample_student):
        d = detention_service.create_detention(sample_student["id"], "R", "2026-03-20")
        detention_service.mark_attended(d["id"])
        updated = detention_service.list_detentions()
        attended = [x for x in updated if x["id"] == d["id"]]
        assert len(attended) == 1 and attended[0]["status"] == "completed"

    def test_mark_missed(self, detention_service, sample_student):
        d = detention_service.create_detention(sample_student["id"], "R", "2026-03-20")
        detention_service.mark_missed(d["id"])
        updated = detention_service.list_detentions()
        missed = [x for x in updated if x["id"] == d["id"]]
        assert len(missed) == 1 and missed[0]["status"] == "missed"

    def test_delete_detention(self, detention_service, sample_student):
        d = detention_service.create_detention(sample_student["id"], "R", "2026-03-20")
        detention_service.delete_detention(d["id"])
        result = detention_service.list_detentions()
        assert all(x["id"] != d["id"] for x in result)
