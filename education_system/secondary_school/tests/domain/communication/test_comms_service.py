"""Tests for CommsService (Communication Log)."""
import pytest


class TestComms:
    def test_add_entry(self, comms_service, sample_student):
        entry = comms_service.add_entry(
            student_id=sample_student["id"],
            contact_with="Mrs Doe",
            summary="Discussed progress",
            contact_type="phone_call",
        )
        assert entry["contact_with"] == "Mrs Doe"
        assert entry["contact_type"] == "phone_call"

    def test_list_entries(self, comms_service, sample_student):
        comms_service.add_entry(sample_student["id"], "Parent A", "Call 1")
        comms_service.add_entry(sample_student["id"], "Parent B", "Call 2")
        entries = comms_service.list_entries()
        assert len(entries) >= 2

    def test_list_entries_filters_by_student_id(self, comms_service, sample_student, sample_student_ks4):
        comms_service.add_entry(sample_student["id"], "Parent A", "Call 1")
        comms_service.add_entry(sample_student_ks4["id"], "Parent B", "Call 2")
        entries = comms_service.list_entries(student_id=sample_student["id"])
        assert all(e["student_id"] == sample_student["id"] for e in entries)

    def test_mark_follow_up_done(self, comms_service, sample_student):
        entry = comms_service.add_entry(
            sample_student["id"], "Parent", "Needs follow-up",
            follow_up_needed=True,
        )
        comms_service.mark_follow_up_done(entry["id"])
        entries = comms_service.list_entries(follow_up_only=True)
        assert all(e["id"] != entry["id"] for e in entries)

    def test_delete_entry(self, comms_service, sample_student):
        entry = comms_service.add_entry(sample_student["id"], "Parent", "Delete me")
        comms_service.delete_entry(entry["id"])
        entries = comms_service.list_entries()
        assert all(e["id"] != entry["id"] for e in entries)
