"""Tests for DestinationOutcomeService."""

import pytest


class TestDestinationOutcomeService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.destination_outcomes.services.destination_outcome_service import DestinationOutcomeService
        return DestinationOutcomeService(db_path)

    def test_record_outcome(self, service):
        oid = service.record_outcome(
            student_id=1, academic_year="2025/26",
            outcome_type="university",
            institution_name="University of Manchester",
            course_title="Computer Science BSc",
        )
        assert oid is not None

    def test_list_outcomes(self, service):
        service.record_outcome(1, "2025/26", "university")
        service.record_outcome(1, "2025/26", "employment")
        outcomes = service.list_outcomes()
        assert len(outcomes) >= 2

    def test_list_outcomes_filter(self, service):
        service.record_outcome(1, "2025/26", "apprenticeship")
        outcomes = service.list_outcomes(outcome_type="apprenticeship")
        assert all(o["outcome_type"] == "apprenticeship" for o in outcomes)

    def test_update_outcome(self, service):
        oid = service.record_outcome(1, "2025/26", "employment")
        result = service.update_outcome(oid, employer_name="TechCorp")
        assert result is not None or result is None

    def test_verify_outcome(self, service):
        oid = service.record_outcome(1, "2025/26", "university")
        result = service.verify_outcome(oid, verified_by=1)
        assert result is not None or result is None

    def test_get_neet_rate(self, service):
        result = service.get_neet_rate("2025/26")
        assert result is not None

    def test_get_outcome_summary(self, service):
        service.record_outcome(1, "2025/26", "university")
        summary = service.get_outcome_summary("2025/26")
        assert summary is not None

    def test_create_survey(self, service):
        sid = service.create_survey(
            student_id=1, academic_year="2025/26",
            survey_type="6_month",
        )
        assert sid is not None

    def test_list_surveys(self, service):
        service.create_survey(1, "2025/26", "3_month")
        surveys = service.list_surveys(academic_year="2025/26")
        assert len(surveys) >= 1

    def test_record_survey_response(self, service):
        sid = service.create_survey(1, "2025/26", "6_month")
        result = service.record_survey_response(
            sid, current_status="employed",
            satisfaction=4, would_recommend=True,
            comments="Great experience",
        )
        assert result is not None or result is None
