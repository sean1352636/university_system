"""Tests for EqualityDiversityService."""

import pytest


class TestEqualityDiversityService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.equality_diversity.services.equality_diversity_service import EqualityDiversityService
        return EqualityDiversityService(db_path)

    def test_create_characteristic(self, service):
        record = service.create_characteristic(
            person_type="student", person_id=1,
            ethnicity="White British",
            disability_status="none",
        )
        assert record is not None

    def test_list_characteristics(self, service):
        service.create_characteristic("student", 1, ethnicity="Asian")
        service.create_characteristic("staff", 2, ethnicity="Black British")
        records = service.list_characteristics()
        assert len(records) >= 2

    def test_get_characteristic(self, service):
        record = service.create_characteristic("student", 1)
        found = service.get_characteristic(record["id"])
        assert found is not None

    def test_update_characteristic(self, service):
        record = service.create_characteristic("student", 1)
        updated = service.update_characteristic(record["id"], preferred_pronouns="they/them")
        assert updated is not None

    def test_delete_characteristic(self, service):
        record = service.create_characteristic("student", 1)
        result = service.delete_characteristic(record["id"])
        assert result is True

    def test_create_assessment(self, service):
        assessment = service.create_assessment(
            policy_or_practice="Admissions Policy",
            assessor="HR Director",
            protected_group="disability",
            impact_type="positive",
        )
        assert assessment is not None

    def test_list_assessments(self, service):
        service.create_assessment("Uniform Policy")
        assessments = service.list_assessments()
        assert len(assessments) >= 1

    def test_create_objective(self, service):
        obj = service.create_objective(
            objective="Increase BAME student enrollment by 10%",
            protected_group="race",
            target="25% BAME enrollment",
            academic_year="2025/26",
        )
        assert obj is not None

    def test_list_objectives(self, service):
        service.create_objective("Objective A")
        objectives = service.list_objectives()
        assert len(objectives) >= 1

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
