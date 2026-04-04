"""Tests for DisciplinaryService."""

import pytest


class TestDisciplinaryService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.disciplinary.services.disciplinary_service import DisciplinaryService
        return DisciplinaryService(db_path)

    def test_create_case(self, service):
        case = service.create_case(
            person_type="student", person_id=1,
            allegation="Repeated absence without authorisation",
        )
        assert case is not None

    def test_list_cases(self, service):
        service.create_case("student", 1, "Case A")
        service.create_case("staff", 2, "Case B")
        cases = service.list_cases()
        assert len(cases) >= 2

    def test_get_case(self, service):
        case = service.create_case("student", 1, "Test case")
        found = service.get_case(case["id"])
        assert found is not None

    def test_update_case(self, service):
        case = service.create_case("student", 1, "Update me")
        updated = service.update_case(case["id"], status="investigating")
        assert updated is not None

    def test_delete_case(self, service):
        case = service.create_case("student", 1, "Delete me")
        result = service.delete_case(case["id"])
        assert result is True

    def test_schedule_hearing(self, service):
        case = service.create_case("student", 1, "Hearing needed")
        result = service.schedule_hearing(
            case["id"], hearing_date="2026-05-01",
            panel="Principal, VP, HR",
        )
        assert result is not None

    def test_record_outcome(self, service):
        case = service.create_case("student", 1, "Outcome pending")
        result = service.record_outcome(
            case["id"], outcome="warning",
            sanction="Written warning",
        )
        assert result is not None

    def test_add_evidence(self, service):
        case = service.create_case("student", 1, "Evidence case")
        evidence = service.add_evidence(
            case["id"], evidence_type="document",
            description="CCTV footage from corridor",
        )
        assert evidence is not None

    def test_list_evidence(self, service):
        case = service.create_case("student", 1, "Evidence list")
        service.add_evidence(case["id"], "witness", "Statement from tutor")
        evidence = service.list_evidence(case["id"])
        assert len(evidence) >= 1

    def test_lodge_appeal(self, service):
        case = service.create_case("student", 1, "Appeal case")
        service.record_outcome(case["id"], "suspension")
        appeal = service.lodge_appeal(
            case_id=case["id"], appellant_id=1,
            appeal_date="2026-05-10",
            grounds="Disproportionate sanction",
        )
        assert appeal is not None

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
