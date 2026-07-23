"""Tests for the PriorLearningService (APL/RPL) — isolated DB."""

import pytest

from education_system.post_18.university_system.modules.domain.academics.prior_learning_recognition.services.prior_learning_service import (
    PriorLearningService,
)


@pytest.fixture()
def service():
    return PriorLearningService()


class TestClaims:
    def test_create_and_get(self, service):
        cid = service.create_claim("STU1", "work_experience",
                                   target_course="BSc CS",
                                   claimant_name="Jane")
        claim = service.get_claim(cid)
        assert claim["claimant_id"] == "STU1"
        assert claim["status"] == "draft"

    def test_create_invalid_type(self, service):
        with pytest.raises(ValueError):
            service.create_claim("STU1", "nonsense_type")

    def test_submit_transitions(self, service):
        cid = service.create_claim("STU1", "prior_qualification")
        assert service.submit_claim(cid) is True
        assert service.get_claim(cid)["status"] == "submitted"

    def test_review_approved(self, service):
        cid = service.create_claim("STU1", "prior_qualification")
        service.submit_claim(cid)
        assert service.review_claim(cid, "approved", reviewed_by="admin") is True
        assert service.get_claim(cid)["status"] == "approved"

    def test_review_invalid_decision(self, service):
        cid = service.create_claim("STU1", "other")
        with pytest.raises(ValueError):
            service.review_claim(cid, "maybe")

    def test_list_filters(self, service):
        service.create_claim("STU1", "other")
        service.create_claim("STU2", "other")
        assert len(service.list_claims()) == 2
        assert len(service.list_claims(claimant_id="STU1")) == 1

    def test_withdraw(self, service):
        cid = service.create_claim("STU1", "other")
        assert service.withdraw_claim(cid) is True
        assert service.get_claim(cid)["status"] == "withdrawn"


class TestEvidence:
    def test_add_and_list(self, service):
        cid = service.create_claim("STU1", "work_experience")
        eid = service.add_evidence(cid, "Cert", evidence_type="certificate",
                                   issuing_body="ACME")
        ev = service.list_evidence(cid)
        assert len(ev) == 1
        assert ev[0]["title"] == "Cert"

    def test_verify(self, service):
        cid = service.create_claim("STU1", "work_experience")
        eid = service.add_evidence(cid, "Cert")
        assert service.verify_evidence(eid, "admin") is True
        assert service.list_evidence(cid)[0]["verified"] == 1


class TestCreditAwards:
    def test_award_updates_claim_total(self, service):
        cid = service.create_claim("STU1", "credit_transfer")
        service.award_credits(cid, 20, module_code="CS100")
        service.award_credits(cid, 10, module_code="CS101")
        assert service.get_claim(cid)["credits_awarded"] == 30
        assert len(service.list_awards(cid)) == 2

    def test_credits_for_student_only_counts_approved(self, service):
        c1 = service.create_claim("STU1", "credit_transfer")
        service.award_credits(c1, 20)
        service.review_claim(c1, "approved")
        c2 = service.create_claim("STU1", "credit_transfer")
        service.award_credits(c2, 15)  # left as draft
        assert service.credits_for_student("STU1") == 20

    def test_awards_for_student(self, service):
        c1 = service.create_claim("STU1", "credit_transfer")
        service.award_credits(c1, 20, module_code="CS100")
        service.review_claim(c1, "partial")
        awards = service.awards_for_student("STU1")
        assert len(awards) == 1
        assert awards[0]["module_code"] == "CS100"


class TestCrossModuleAndStats:
    def test_create_draft_from_crm_prospect(self, service):
        cid = service.create_draft_from_crm_prospect(42, prospect_name="Bob",
                                                     intended_major="CS")
        claim = service.get_claim(cid)
        assert claim["claimant_id"] == "prospect:42"
        assert claim["claim_type"] == "other"

    def test_create_evidence_from_placement_reuses_draft(self, service):
        cid1 = service.create_evidence_from_placement(
            "STU1", employer="ACME", total_hours=100, signed_off_hours=80)
        cid2 = service.create_evidence_from_placement(
            "STU1", employer="ACME2", total_hours=50, signed_off_hours=40)
        assert cid1 == cid2  # same draft work_experience claim reused
        assert len(service.list_evidence(cid1)) == 2

    def test_create_claim_from_clearing_missing(self, service):
        assert service.create_claim_from_clearing(99999) is None

    def test_statistics(self, service):
        c1 = service.create_claim("STU1", "work_experience", credits_requested=30)
        service.award_credits(c1, 20)
        service.review_claim(c1, "approved")
        service.create_claim("STU2", "other")
        stats = service.get_statistics()
        assert stats["total_claims"] == 2
        assert stats["credits_awarded"] == 20
        assert stats["approval_rate_pct"] == 100.0
