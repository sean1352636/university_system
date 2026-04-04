"""Tests for PreventDutyService."""

import pytest


class TestPreventDutyService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.prevent_duty.services.prevent_duty_service import PreventDutyService
        return PreventDutyService(db_path)

    def test_create_referral(self, service):
        referral = service.create_referral(
            subject_name="John Doe",
            concern_details="Expressing extremist views in class",
            reported_by=1,
            risk_level="medium",
        )
        assert referral is not None

    def test_list_referrals(self, service):
        service.create_referral("Student A", "Concern 1", reported_by=1, risk_level="low")
        service.create_referral("Student B", "Concern 2", reported_by=1, risk_level="high")
        referrals = service.list_referrals()
        assert len(referrals) >= 2

    def test_get_referral(self, service):
        ref = service.create_referral("Test Subject", "Details here", reported_by=1)
        rid = ref if isinstance(ref, int) else ref.get("id", ref)
        found = service.get_referral(rid)
        assert found is not None

    def test_update_referral(self, service):
        ref = service.create_referral("Subject", "Update test", reported_by=1)
        rid = ref if isinstance(ref, int) else ref.get("id", ref)
        result = service.update_referral(rid, risk_level="high")
        assert result is not None

    def test_delete_referral(self, service):
        ref = service.create_referral("Subject", "Delete test", reported_by=1)
        rid = ref if isinstance(ref, int) else ref.get("id", ref)
        result = service.delete_referral(rid)
        assert result is True or result is None

    def test_escalate_to_channel(self, service):
        ref = service.create_referral("Subject", "Escalate test", reported_by=1, risk_level="high")
        rid = ref if isinstance(ref, int) else ref.get("id", ref)
        result = service.escalate_to_channel(rid, channel_reference="CH-2026-001")
        assert result is not None

    def test_create_training(self, service):
        training = service.create_training(
            staff_id=1, training_type="basic",
            completed_date="2026-01-15",
            expiry_date="2027-01-15",
        )
        assert training is not None

    def test_list_training(self, service):
        service.create_training(staff_id=1, completed_date="2026-01-15")
        records = service.list_training()
        assert len(records) >= 1

    def test_get_expiring_training(self, service):
        service.create_training(
            staff_id=1, completed_date="2026-01-15",
            expiry_date="2026-04-15",
        )
        expiring = service.get_expiring_training(within_days=30)
        assert isinstance(expiring, list)

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
