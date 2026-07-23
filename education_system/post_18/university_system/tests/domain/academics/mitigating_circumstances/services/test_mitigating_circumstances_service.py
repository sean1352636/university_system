"""Tests for the MitigatingCircumstancesService (isolated DB)."""

import pytest

from education_system.post_18.university_system.modules.domain.academics.mitigating_circumstances.services.mitigating_circumstances_service import (
    MitigatingCircumstancesService,
)


@pytest.fixture()
def service():
    return MitigatingCircumstancesService()


class TestClaims:
    def test_submit_and_get(self, service):
        cid = service.submit_claim(student_id="S1", module_code="CS101",
                                   grounds="medical", description="Ill")
        claim = service.get_claim(cid)
        assert claim["student_id"] == "S1"
        assert claim["status"] == "submitted"

    def test_submit_requires_student(self, service):
        with pytest.raises(ValueError):
            service.submit_claim(module_code="CS101")

    def test_submit_invalid_grounds(self, service):
        with pytest.raises(ValueError):
            service.submit_claim(student_id="S1", grounds="not_valid")

    def test_submit_from_dict(self, service):
        cid = service.submit_claim({"student_id": "S9", "grounds": "bereavement"})
        assert service.get_claim(cid)["grounds"] == "bereavement"

    def test_list_claims_filters(self, service):
        service.submit_claim(student_id="S1", grounds="medical")
        service.submit_claim(student_id="S2", grounds="personal")
        assert len(service.list_claims()) == 2
        assert len(service.list_claims(student_id="S1")) == 1

    def test_update_status_validation(self, service):
        cid = service.submit_claim(student_id="S1")
        assert service.update_claim_status(cid, "under_review") is True
        with pytest.raises(ValueError):
            service.update_claim_status(cid, "bogus")

    def test_withdraw(self, service):
        cid = service.submit_claim(student_id="S1")
        assert service.withdraw_claim(cid) is True
        assert service.get_claim(cid)["status"] == "withdrawn"


class TestEvidence:
    def test_add_evidence_advances_status(self, service):
        cid = service.submit_claim(student_id="S1")
        eid = service.add_evidence(cid, evidence_type="letter",
                                   description="GP note")
        assert eid > 0
        assert service.get_claim(cid)["status"] == "under_review"
        evidence = service.list_evidence(cid)
        assert len(evidence) == 1

    def test_verify_evidence(self, service):
        cid = service.submit_claim(student_id="S1")
        eid = service.add_evidence(cid, evidence_type="letter")
        assert service.verify_evidence(eid, "admin") is True
        assert service.list_evidence(cid)[0]["verified"] == 1


class TestPanels:
    def test_schedule_assign_decide(self, service):
        cid = service.submit_claim(student_id="S1")
        pid = service.schedule_panel("2026-06-15", chair="Dr Chair")
        service.assign_claim_to_panel(pid, cid)
        assert service.get_claim(cid)["status"] == "panel_scheduled"
        items = service.get_panel_items(pid)
        assert len(items) == 1
        assert service.record_panel_decision(pid, cid, "approved",
                                              "extension_granted") is True
        assert service.get_claim(cid)["status"] == "approved"

    def test_decision_invalid_outcome(self, service):
        cid = service.submit_claim(student_id="S1")
        pid = service.schedule_panel("2026-06-15")
        service.assign_claim_to_panel(pid, cid)
        with pytest.raises(ValueError):
            service.record_panel_decision(pid, cid, "approved", "bad_outcome")


class TestExtensions:
    def test_grant_extension_derives_new_deadline(self, service):
        cid = service.submit_claim(student_id="S1", module_code="CS101",
                                   assessment_ref="A1")
        ext_id = service.grant_extension(cid, "2026-05-01", extension_days=7)
        exts = service.list_extensions(claim_id=cid)
        assert len(exts) == 1
        assert exts[0]["new_deadline"] == "2026-05-08"
        assert exts[0]["extension_days"] == 7

    def test_grant_extension_derives_days_from_new_deadline(self, service):
        cid = service.submit_claim(student_id="S1")
        service.grant_extension(cid, "2026-05-01", new_deadline="2026-05-11")
        exts = service.list_extensions(claim_id=cid)
        assert exts[0]["extension_days"] == 10

    def test_grant_extension_unknown_claim(self, service):
        with pytest.raises(ValueError):
            service.grant_extension(99999, "2026-05-01", extension_days=3)

    def test_get_active_and_mark_applied(self, service):
        cid = service.submit_claim(student_id="S1", module_code="CS101",
                                   assessment_ref="A1")
        eid = service.grant_extension(cid, "2026-05-01", extension_days=5,
                                      module_code="CS101", assessment_ref="A1")
        active = service.get_active_extension("S1", "CS101", "A1")
        assert active is not None
        assert service.mark_extension_applied(eid) is True
        assert service.list_extensions(claim_id=cid)[0]["applied"] == 1


class TestStatistics:
    def test_statistics(self, service):
        c1 = service.submit_claim(student_id="S1", grounds="medical")
        service.submit_claim(student_id="S2", grounds="personal")
        service.grant_extension(c1, "2026-05-01", extension_days=5)
        stats = service.claim_statistics()
        assert stats["total_claims"] == 2
        assert stats["extensions_granted"] == 1
        assert stats["by_grounds"]["medical"] == 1
