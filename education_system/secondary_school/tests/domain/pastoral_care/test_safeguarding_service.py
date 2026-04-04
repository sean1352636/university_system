"""Tests for SafeguardingService."""
import pytest
from education_system.secondary_school.core.exceptions import SafeguardingError


class TestLogConcern:
    def test_log_concern_creates_record(self, safeguarding_service, sample_student):
        c = safeguarding_service.log_concern(
            student_id=sample_student["id"],
            reported_by="Mrs Taylor",
            concern_type="welfare",
            severity="low",
            description="Student appears withdrawn",
        )
        assert c["student_id"] == sample_student["id"]
        assert c["reported_by"] == "Mrs Taylor"
        assert c["concern_type"] == "welfare"
        assert c["severity"] == "low"
        assert c["description"] == "Student appears withdrawn"
        assert c["is_resolved"] == 0

    def test_log_concern_with_high_severity(self, safeguarding_service, sample_student):
        c = safeguarding_service.log_concern(
            student_id=sample_student["id"],
            reported_by="Mr Adams",
            concern_type="child_protection",
            severity="high",
            description="Visible bruising",
            action_taken="Referred to DSL",
            referred_to="DSL",
        )
        assert c["severity"] == "high"
        assert c["concern_type"] == "child_protection"
        assert c["action_taken"] == "Referred to DSL"
        assert c["referred_to"] == "DSL"


class TestListConcerns:
    def test_list_returns_all(self, safeguarding_service, sample_student):
        safeguarding_service.log_concern(
            sample_student["id"], "Staff A", description="Concern 1",
        )
        safeguarding_service.log_concern(
            sample_student["id"], "Staff B", description="Concern 2",
        )
        result = safeguarding_service.list_concerns()
        assert len(result) >= 2

    def test_list_filter_by_resolved(self, safeguarding_service, sample_student):
        c1 = safeguarding_service.log_concern(
            sample_student["id"], "Staff A", description="Open concern",
        )
        c2 = safeguarding_service.log_concern(
            sample_student["id"], "Staff B", description="Resolved concern",
        )
        safeguarding_service.resolve_concern(c2["id"], outcome="No further action")
        unresolved = safeguarding_service.list_concerns(is_resolved=False)
        resolved = safeguarding_service.list_concerns(is_resolved=True)
        assert all(x["is_resolved"] == 0 for x in unresolved)
        assert all(x["is_resolved"] == 1 for x in resolved)
        assert any(x["id"] == c1["id"] for x in unresolved)
        assert any(x["id"] == c2["id"] for x in resolved)


class TestConcernActions:
    def test_resolve_concern(self, safeguarding_service, sample_student):
        c = safeguarding_service.log_concern(
            sample_student["id"], "Staff A", description="To resolve",
        )
        safeguarding_service.resolve_concern(c["id"], outcome="Resolved internally")
        resolved = safeguarding_service.list_concerns(is_resolved=True)
        rec = [x for x in resolved if x["id"] == c["id"]]
        assert len(rec) == 1
        assert rec[0]["outcome"] == "Resolved internally"

    def test_update_concern(self, safeguarding_service, sample_student):
        c = safeguarding_service.log_concern(
            sample_student["id"], "Staff A",
            severity="low", description="Initial concern",
        )
        safeguarding_service.update_concern(
            c["id"], severity="high", action_taken="Escalated to headteacher",
        )
        concerns = safeguarding_service.list_concerns()
        updated = [x for x in concerns if x["id"] == c["id"]][0]
        assert updated["severity"] == "high"
        assert updated["action_taken"] == "Escalated to headteacher"

    def test_delete_concern(self, safeguarding_service, sample_student):
        c = safeguarding_service.log_concern(
            sample_student["id"], "Staff A", description="To delete",
        )
        safeguarding_service.delete_concern(c["id"])
        result = safeguarding_service.list_concerns()
        assert all(x["id"] != c["id"] for x in result)
