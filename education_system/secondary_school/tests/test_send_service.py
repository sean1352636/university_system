"""Tests for SENDService."""
import pytest
from education_system.secondary_school.core.exceptions import SENDError


class TestCreateRecord:
    def test_create_record(self, send_service, sample_student):
        r = send_service.create_record(
            student_id=sample_student["id"],
            sen_type="SEN Support",
            primary_need="Cognition & Learning",
            key_worker="Mrs Green",
            diagnosis="Dyslexia",
        )
        assert r["student_id"] == sample_student["id"]
        assert r["sen_type"] == "SEN Support"
        assert r["primary_need"] == "Cognition & Learning"
        assert r["key_worker"] == "Mrs Green"
        assert r["diagnosis"] == "Dyslexia"
        assert r["status"] == "active"

    def test_create_record_with_ehcp(self, send_service, sample_student):
        r = send_service.create_record(
            student_id=sample_student["id"],
            sen_type="EHCP",
            primary_need="Social, Emotional & Mental Health",
            ehcp=True,
            strategies="Small group support, extra time",
            access_arrangements="25% extra time in exams",
        )
        assert r["sen_type"] == "EHCP"
        assert r["ehcp"] == 1
        assert r["strategies"] == "Small group support, extra time"
        assert r["access_arrangements"] == "25% extra time in exams"


class TestListRecords:
    def test_list_returns_records(self, send_service, sample_student, sample_student_ks4):
        send_service.create_record(sample_student["id"])
        send_service.create_record(sample_student_ks4["id"])
        result = send_service.list_records()
        assert len(result) >= 2

    def test_list_filter_by_status(self, send_service, sample_student, sample_student_ks4):
        r1 = send_service.create_record(sample_student["id"])
        r2 = send_service.create_record(sample_student_ks4["id"])
        send_service.update_record(r2["id"], status="closed")
        active = send_service.list_records(status="active")
        assert len(active) == 1
        assert active[0]["id"] == r1["id"]


class TestUpdateRecord:
    def test_update_modifies_fields(self, send_service, sample_student):
        r = send_service.create_record(
            sample_student["id"], sen_type="SEN Support",
        )
        send_service.update_record(
            r["id"], sen_type="EHCP", ehcp=1,
            key_worker="Mr White", notes="Upgraded to EHCP",
        )
        records = send_service.list_records()
        updated = [x for x in records if x["id"] == r["id"]][0]
        assert updated["sen_type"] == "EHCP"
        assert updated["ehcp"] == 1
        assert updated["key_worker"] == "Mr White"
        assert updated["notes"] == "Upgraded to EHCP"


class TestDeleteRecord:
    def test_delete_removes_record(self, send_service, sample_student):
        r = send_service.create_record(sample_student["id"])
        send_service.delete_record(r["id"])
        result = send_service.list_records()
        assert all(x["id"] != r["id"] for x in result)


class TestProvisions:
    def test_add_provision(self, send_service, sample_student):
        r = send_service.create_record(sample_student["id"])
        p = send_service.add_provision(
            send_record_id=r["id"],
            provision_type="In-class support",
            description="TA support in Maths and English",
            frequency="Daily",
            staff_responsible="Mrs Clark",
            start_date="2026-03-01",
        )
        assert p["send_record_id"] == r["id"]
        assert p["provision_type"] == "In-class support"
        assert p["description"] == "TA support in Maths and English"
        assert p["frequency"] == "Daily"

    def test_list_provisions(self, send_service, sample_student):
        r = send_service.create_record(sample_student["id"])
        send_service.add_provision(r["id"], "Speech therapy", frequency="Weekly")
        send_service.add_provision(r["id"], "Occupational therapy", frequency="Fortnightly")
        provisions = send_service.list_provisions(r["id"])
        assert len(provisions) == 2
        types = {p["provision_type"] for p in provisions}
        assert "Speech therapy" in types
        assert "Occupational therapy" in types
