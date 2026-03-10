"""Tests for FundingService."""

import pytest

from education_system.college_system.modules.domain.funding.services.funding_service import FundingService
from education_system.college_system.core.exceptions import FundingError


class TestFundingRecords:
    def test_create_funding_record(self, db_path, sample_student):
        svc = FundingService(db_path)
        record = svc.create_funding_record(
            sample_student["id"], learning_aim="BTEC IT",
            planned_hours=540, funding_model="16-19",
        )
        assert record["learning_aim"] == "BTEC IT"
        assert record["planned_hours"] == 540
        assert record["completion_status"] == "in_progress"

    def test_complete_record(self, db_path, sample_student):
        svc = FundingService(db_path)
        record = svc.create_funding_record(sample_student["id"], learning_aim="A-Level Maths")
        completed = svc.complete_funding_record(record["id"])
        assert completed["completion_status"] == "completed"
        assert completed["outcome"] == "achieved"

    def test_withdraw_record(self, db_path, sample_student):
        svc = FundingService(db_path)
        record = svc.create_funding_record(sample_student["id"])
        withdrawn = svc.withdraw_funding_record(record["id"])
        assert withdrawn["completion_status"] == "withdrawn"

    def test_hours_summary(self, db_path, sample_student):
        svc = FundingService(db_path)
        svc.create_funding_record(sample_student["id"], planned_hours=100)
        svc.create_funding_record(sample_student["id"], planned_hours=200)
        summary = svc.get_hours_summary(sample_student["id"])
        assert summary["total_planned"] == 300


class TestEvidence:
    def test_add_and_verify_evidence(self, db_path, sample_student):
        svc = FundingService(db_path)
        record = svc.create_funding_record(sample_student["id"])
        ev = svc.add_evidence(record["id"], "enrollment_form")
        assert ev["verified"] == 0

        verified = svc.verify_evidence(ev["id"], 1)
        assert verified["verified"] == 1


class TestRules:
    def test_create_rule(self, db_path):
        svc = FundingService(db_path)
        rule = svc.create_rule("RULE001", "Min 540 hours", "hours")
        assert rule["rule_code"] == "RULE001"
        assert rule["is_active"] == 1


class TestResits:
    def test_create_resit(self, db_path, sample_student):
        svc = FundingService(db_path)
        resit = svc.create_resit(sample_student["id"], "english", gcse_grade_on_entry="3")
        assert resit["subject"] == "english"
        assert resit["status"] == "active"

    def test_update_resit(self, db_path, sample_student):
        svc = FundingService(db_path)
        resit = svc.create_resit(sample_student["id"], "maths")
        updated = svc.update_resit(resit["id"], status="achieved", latest_result="4")
        assert updated["status"] == "achieved"
        assert updated["latest_result"] == "4"

    def test_resit_summary(self, db_path, sample_student):
        svc = FundingService(db_path)
        svc.create_resit(sample_student["id"], "english")
        svc.create_resit(sample_student["id"], "maths")
        summary = svc.get_resit_summary()
        assert len(summary["subjects"]) == 2
