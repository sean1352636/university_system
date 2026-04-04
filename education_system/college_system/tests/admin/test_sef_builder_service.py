"""Tests for SEFBuilderService."""

import pytest


class TestSEFBuilderService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.sef_builder.services.sef_builder_service import SEFBuilderService
        return SEFBuilderService(db_path)

    @pytest.fixture
    def sample_sef(self, service):
        return service.create_sef(
            academic_year="2025/26",
            title="Annual SEF 2025-26",
            created_by=1,
        )

    def test_create_sef(self, service):
        sef = service.create_sef(
            academic_year="2025/26", title="Test SEF",
            created_by=1,
        )
        assert sef is not None

    def test_list_sefs(self, service):
        service.create_sef("2025/26", "SEF A", 1)
        sefs = service.list_sefs()
        assert len(sefs) >= 1

    def test_get_sef(self, service, sample_sef):
        sef_id = sample_sef if isinstance(sample_sef, int) else sample_sef.get("id", sample_sef)
        found = service.get_sef(sef_id)
        assert found is not None

    def test_add_judgement_area(self, service, sample_sef):
        sef_id = sample_sef if isinstance(sample_sef, int) else sample_sef.get("id", sample_sef)
        area = service.add_judgement_area(
            sef_id=sef_id, area_name="Quality of Education",
            area_number=1, self_grade="good",
        )
        assert area is not None

    def test_list_judgement_areas(self, service, sample_sef):
        sef_id = sample_sef if isinstance(sample_sef, int) else sample_sef.get("id", sample_sef)
        service.add_judgement_area(sef_id, "Leadership", 2, self_grade="good")
        areas = service.list_judgement_areas(sef_id)
        assert len(areas) >= 1

    def test_add_evidence_link(self, service, sample_sef):
        sef_id = sample_sef if isinstance(sample_sef, int) else sample_sef.get("id", sample_sef)
        area = service.add_judgement_area(sef_id, "Behaviour", 3, self_grade="outstanding")
        area_id = area if isinstance(area, int) else area.get("id", area)
        evidence = service.add_evidence_link(
            judgement_area_id=area_id,
            evidence_type="data",
            evidence_description="Exclusion rates reduced by 15%",
        )
        assert evidence is not None

    def test_list_evidence(self, service, sample_sef):
        sef_id = sample_sef if isinstance(sample_sef, int) else sample_sef.get("id", sample_sef)
        area = service.add_judgement_area(sef_id, "Outcomes", 4, self_grade="good")
        area_id = area if isinstance(area, int) else area.get("id", area)
        service.add_evidence_link(area_id, "data", "A-level results above national avg")
        evidence = service.list_evidence(area_id)
        assert len(evidence) >= 1

    def test_get_sef_summary(self, service, sample_sef):
        sef_id = sample_sef if isinstance(sample_sef, int) else sample_sef.get("id", sample_sef)
        summary = service.get_sef_summary(sef_id)
        assert summary is not None

    def test_export_sef(self, service, sample_sef):
        sef_id = sample_sef if isinstance(sample_sef, int) else sample_sef.get("id", sample_sef)
        result = service.export_sef(sef_id)
        assert result is not None
