"""Tests for SelfAssessmentService."""

import pytest


class TestSelfAssessmentService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.self_assessment.services.self_assessment_service import SelfAssessmentService
        return SelfAssessmentService(db_path)

    @pytest.fixture
    def sample_section(self, service):
        return service.create_section(
            section_name="Quality of Education",
            section_number=1, academic_year="2025/26",
            self_grade="Good",
            strengths="Strong A-level results",
            areas_for_improvement="Vocational completion rates",
        )

    def test_create_section(self, service):
        section = service.create_section(
            section_name="Leadership", section_number=2,
        )
        assert section is not None

    def test_list_sections(self, service):
        service.create_section(section_name="S1")
        service.create_section(section_name="S2")
        sections = service.list_sections()
        assert len(sections) >= 2

    def test_get_section(self, service, sample_section):
        sid = sample_section if isinstance(sample_section, int) else sample_section.get("id", sample_section)
        found = service.get_section(sid)
        assert found is not None

    def test_update_section(self, service, sample_section):
        sid = sample_section if isinstance(sample_section, int) else sample_section.get("id", sample_section)
        result = service.update_section(sid, self_grade="Outstanding")
        assert result is not None

    def test_delete_section(self, service, sample_section):
        sid = sample_section if isinstance(sample_section, int) else sample_section.get("id", sample_section)
        result = service.delete_section(sid)
        assert result is True or result is None

    def test_create_action(self, service, sample_section):
        sid = sample_section if isinstance(sample_section, int) else sample_section.get("id", sample_section)
        action = service.create_action(
            sef_section_id=sid,
            action_description="Improve vocational pass rates",
            responsible_person="Head of Vocational",
            target_date="2026-07-01",
        )
        assert action is not None

    def test_list_actions(self, service, sample_section):
        sid = sample_section if isinstance(sample_section, int) else sample_section.get("id", sample_section)
        service.create_action(sid, "Action 1")
        actions = service.list_actions(sef_section_id=sid)
        assert len(actions) >= 1

    def test_create_checklist_item(self, service):
        item = service.create_checklist_item(
            category="safeguarding",
            item="SCR up to date",
            responsible_person="DSL",
        )
        assert item is not None

    def test_list_checklist(self, service):
        service.create_checklist_item("governance", "Board minutes filed")
        items = service.list_checklist()
        assert len(items) >= 1

    def test_toggle_ready(self, service):
        item = service.create_checklist_item("data", "Results analysis complete")
        item_id = item if isinstance(item, int) else item.get("id", item)
        result = service.toggle_ready(item_id)
        assert result is not None

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
