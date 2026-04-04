"""Tests for StudentWellbeingService."""

import pytest


class TestStudentWellbeingService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.student_wellbeing.services.student_wellbeing_service import StudentWellbeingService
        return StudentWellbeingService(db_path)

    def test_create_referral(self, service):
        ref = service.create_referral(
            student_id=1, concern_details="Anxiety about exams",
            concern_category="mental_health", risk_level="medium",
        )
        assert ref is not None

    def test_list_referrals(self, service):
        service.create_referral(1, "Concern A")
        service.create_referral(1, "Concern B")
        refs = service.list_referrals()
        assert len(refs) >= 2

    def test_get_referral(self, service):
        ref = service.create_referral(1, "Test concern")
        rid = ref if isinstance(ref, int) else ref.get("id", ref)
        found = service.get_referral(rid)
        assert found is not None

    def test_update_referral(self, service):
        ref = service.create_referral(1, "Update test")
        rid = ref if isinstance(ref, int) else ref.get("id", ref)
        updated = service.update_referral(rid, risk_level="high")
        assert updated is not None

    def test_delete_referral(self, service):
        ref = service.create_referral(1, "Delete test")
        rid = ref if isinstance(ref, int) else ref.get("id", ref)
        result = service.delete_referral(rid)
        assert result is True or result is None

    def test_resolve_referral(self, service):
        ref = service.create_referral(1, "Resolve me")
        rid = ref if isinstance(ref, int) else ref.get("id", ref)
        result = service.resolve_referral(rid, outcome="Counselling completed")
        assert result is not None

    def test_create_log(self, service):
        log = service.create_log(student_id=1)
        assert log is not None

    def test_list_logs(self, service):
        service.create_log(student_id=1)
        logs = service.list_logs(student_id=1)
        assert len(logs) >= 1

    def test_create_session(self, service):
        session = service.create_session(
            student_id=1, session_date="2026-04-01",
            session_type="counselling",
        )
        assert session is not None

    def test_list_sessions(self, service):
        service.create_session(1, "2026-04-01")
        sessions = service.list_sessions(student_id=1)
        assert len(sessions) >= 1

    def test_get_high_risk_students(self, service):
        result = service.get_high_risk_students()
        assert isinstance(result, list)

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
